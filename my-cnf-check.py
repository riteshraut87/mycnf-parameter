import sys
import subprocess
import pymysql
import json
import csv
import boto3


# Below Code will read parameter store and will create dictionary of all values. Replace parameter store name in ParameterName variable
client = boto3.client('ssm',region_name='us-east-1')
ParameterName = '/PARAMETER-STORENAME/replaceit'
resp= client.get_parameter(Name = ParameterName)

print(len(resp))
for i in resp['Parameter']:
    if i == 'Value':
       all_defaults = resp['Parameter'][i]

json_acceptable_string = all_defaults.replace("'", "\"")
parameter_grpup_dictionary = json.loads(json_acceptable_string)

print(parameter_grpup_dictionary)



# Below code will read my.cnf file and will make dictionary  of all parameters specified in mysqld section . Replace my.cnf location 

p = subprocess.Popen("my_print_defaults --defaults-file=/etc/my.cnf mysqld  | tr '=' '\t'  > /tmp/test123.txt;sed -i 's/--//g' /tmp/test123.txt; ", stdout=subprocess.PIPE, shell=True)
#print(p.communicate())
p.communicate()


d = {}
with open('/tmp/test123.txt', 'r') as csv_file:
        for row in csv.reader(csv_file, delimiter='\t'):
            d[row[0]] = row[1:]


# This mini function is written to check if value is integer or IP
def checkInt(str):
    try:
        int(str)
        return True
    except ValueError:
        return False


print(f"values before conversions are {d}")


# My.cnf may have values given in terms of MB/KB/G, so we will convert these values to integers for comparison.
for i in d:
        if d[i]:
            val= d[i][0]
            # print(val)
            if val[0].isdigit():
                if val[-1].isalpha():
                    last_char = val[-1].upper()
                    digit_val = int(val[:-1] )
                    # print(digit_val)
                    if last_char == 'M':
                        new_val = digit_val * 1024 * 1024
                        d[i] = new_val
                    elif last_char == 'K':
                        new_val = digit_val * 1024
                        d[i] = new_val
                    elif last_char == 'G':
                        new_val = digit_val * 1024 * 1024 * 1024
                        d[i] = new_val
                        # print(f"{i} {new_val}")
                else:  # Below if loop will check if value obtained in numbers is integer of float ( '127.0.0.1' ).
                    # This is important as value of number/integer are needed to be passed as integer for comparison , which will be done in further code.
                    if checkInt(val):
                        d[i] = int(val)
                    else:
                        d[i] = val
            else:   # else condition is for non-numeric values - get it out of list
                d[i] = val
        else: # else condition is for taking blank values out of list
            d[i] = ''

print(f"My.cnf has below parameters \n {d}")



final_variables_to_alter = {}
final_variables_to_go_in_my_cnf = {}
static_variable = {}



# Below loop will find if any new values are given in parameter store or any values are different in parameter store and my.cnf
for pvalue in parameter_grpup_dictionary:
    if pvalue in d:
        # print(f"This variable is present in my.cnf : {pvalue}")
        # Once Key is Present we will go for value comparison
        if d[pvalue] == parameter_grpup_dictionary[pvalue]:
           continue
           # print(f"This variable is present in my.cnf : {pvalue} & value is same !!")
        else:
            print(f"This variable is present in my.cnf : {pvalue}  & value is different Current:{d[pvalue]} .. New Value {parameter_grpup_dictionary[pvalue]}")
            final_variables_to_alter[pvalue] = parameter_grpup_dictionary[pvalue]
    else:
        print(f"This is new variable '{pvalue}' & we need to add it in my.cnf. Value to be updated is : {parameter_grpup_dictionary[pvalue]} ")
        final_variables_to_alter[pvalue] = parameter_grpup_dictionary[pvalue]
        final_variables_to_go_in_my_cnf[pvalue] = parameter_grpup_dictionary[pvalue]


print(final_variables_to_alter)



# If no variables to change then it will exit the script
if not final_variables_to_alter:
    print("There are no changes noted  !!.. All Looks Good !!")
    exit()


# Below section will make changes in mysql database (Query Execution)
for variable1 in final_variables_to_alter:
    dbPassword="******"
    dbUser = "root"
    hostip='localhost'
    connectionObject = pymysql.connect(host=hostip , user=dbUser, password=dbPassword, connect_timeout=5)
    cursorObject = connectionObject.cursor()
    sqlQuery = f"show global variables like '{variable1}';"
    cursorObject.execute(sqlQuery)
    data1 = cursorObject.fetchone()
    current_value=data1[1]
    proposed_value = final_variables_to_alter[variable1]
    print(f" Current value of {variable1} in DB is {current_value} & Proposed value is {proposed_value}")
    sqlQuery = f"set global {variable1} = {proposed_value} ;"
    print(sqlQuery)
    flag = "0"
    #### Below code is written to check if the parameter is static or dynamic. Static variables will give error no  1238
    ## We get following error for dynamic variable
    ### pymysql.err.InternalError: (1238, "Variable 'innodb_log_file_size' is a read only variable")
    try:
        cursorObject.execute(sqlQuery)
        flag = "0"
        print("Variable Value changed Successfully !!")
    except Exception as e:
        # print(e)
        flag = e.args[0]
        error_MY = e.args[1]
    if flag == "0":
        sqlQuery = f"show global variables like '{variable1}';"
        cursorObject.execute(sqlQuery)
        data1 = cursorObject.fetchone()
        new_value = data1[1]
        print(f" OLD value of {variable1} was {current_value} & New value is {new_value}")
    elif flag == 1238:  ## If variable is dynamic it will be saved in dictionary {static_variable}
        print(f"Variable {variable1} is a Static Variable")
        sqlQuery = f"show global variables like '{variable1}';"
        cursorObject.execute(sqlQuery)
        data1 = cursorObject.fetchone()
        new_value = data1[1]
        print(f" Value of variable {variable1} is not changed current_value: {current_value}")
        static_variable[variable1] = proposed_value
    else:
        print(f"Some other error !! \nError Code:{flag} \nError Message:{error_MY} for Variable{variable1} ")

# Below section  will make changes in my.cnf file
p = subprocess.Popen(" > /tmp/missing_data.txt ", stdout=subprocess.PIPE, shell=True)
p.communicate()

for new_variable in final_variables_to_alter:
    variable_value = final_variables_to_alter[new_variable]
    print(f"{new_variable} = {variable_value}")
    original_stdout = sys.stdout
    p = subprocess.Popen(f"sed -i '/{new_variable}/d'  /etc/my.cnf", stdout=subprocess.PIPE, shell=True)
    print(p.communicate())
    with open('/tmp/missing_data.txt', 'a') as f:
        sys.stdout = f # Change the standard output to the file we created.
        print(f"{new_variable} = {variable_value}")
        sys.stdout = original_stdout # Reset the standard output to its original value
    print(f"Below New  variables Or variables with new value are added in my.cnf \n{new_variable} \nWe will need MYSQL service restart for variables \n{static_variable}")


p = subprocess.Popen("sed -i '/\[mysqld\]/r /tmp/missing_data.txt'  /etc/my.cnf ", stdout=subprocess.PIPE, shell=True)
p.communicate()

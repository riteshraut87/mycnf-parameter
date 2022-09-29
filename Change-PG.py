import json
import boto3
import time
from datetime import datetime

def lambda_handler(event, context):
    dt = datetime.now()
    ts = datetime.timestamp(dt)
    dt = datetime.fromtimestamp(ts)

    # CMD =f"('sh -x /home/ec2-user/script-call-python.sh > /home/ec2-user/script-call-python.log{dt} 2>&1')"
    # print(CMD)
    ssm_client = boto3.client('ssm')
    response = ssm_client.send_command(
                InstanceIds=['i-0be6b4e1709698a93'],
                DocumentName="AWS-RunShellScript",
                Parameters={'commands': ['sh -x /home/ec2-user/script-call-python.sh > /home/ec2-user/script-call-python.log 2>&1']},
                )
    time.sleep(2)
    
    command_id = response['Command']['CommandId']
    time.sleep(2)

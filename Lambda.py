import json
import boto3
from datetime import datetime
from datetime import timedelta 
import csv

# session = boto3.Session(profile_name="aws_ec2_iam_user", region_name="us-east-1")
session = boto3.Session(region_name="us-east-1")

ec2 = session.resource(service_name="ec2")
cloudwatch = boto3.client('cloudwatch')

Filters = [{
    'Name': 'instance-state-name',
    'Values': ['running']
}]

def get_instance_list():
    # Use the filter() method of the instances collection to retrieve
    # all running EC2 instances.
    runningInstancesId = []
    statusCode = 400
    try:
        instances = ec2.instances.filter(Filters = Filters)
        # instantiate empty array
        for instance in instances:
            # get all instance-id
            runningInstancesId.append(instance.id)
        statusCode = 200
        print (instances)
    except Exception as e:
        print("Something went wrong while getting the Instance list!!", e)

    return {
        'statusCode': statusCode,
        'body': runningInstancesId
    }

def get_metrics(data):
    # https://docs.aws.amazon.com/cli/latest/reference/cloudwatch/get-metric-data.html
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudwatch.html#CloudWatch.Client.get_metric_statistics
    metrics_stats = []
    print(data)
    for metric in data['metricNames']:
        response = cloudwatch.get_metric_statistics(
            Namespace = data['namespace'],
            Period = data['period'],
            StartTime = data['startTime'],
            EndTime = data['endTime'],
            MetricName = metric,
            Statistics=['Average'], Unit='Percent',
            Dimensions = [
                {'Name': 'InstanceId', 'Value': data['instanceId']}
            ])
        metrics_stats.append(response)
    return metrics_stats
    
def upload_s3(filePath, bucketName, fileName):
    s3 = boto3.resource('s3')
    s3.meta.client.upload_file(filePath, bucketName, fileName)
    
def create_csv(fileName, data):
    with open(fileName, 'w+') as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        filewriter.writerow(['DateTime', datetime.now()])
        filewriter.writerow(['EC2 instance ID', data['instanceId']])
        filewriter.writerow(['MetricName', data['metricName']])
        filewriter.writerow(['MetricValue', "{} %".format(data['metricValue'])])

def lambda_handler(event, context):

    res = get_instance_list()
    if res['statusCode'] == 200: 
        for instance in res['body']:
            metrics_data = {
                'namespace': 'AWS/EC2', 
                'metricNames': ['CPUUtilization','NetworkIn','NetworkOut', 'DiskReadOps', 'DiskWriteOps', 'DiskReadBytes', 'DiskWriteBytes'], 
                'period': 300, 
                'startTime': datetime.now() - timedelta(hours=3), 
                'endTime': datetime.now() - timedelta(hours=1), 
                'instanceId': instance,
            }
            res = get_metrics(metrics_data)[0]
            metricAvgValue = 0
            sum = 0
            print(res['Datapoints'])
            for data in res['Datapoints']:
                sum += data['Average']
            
            metricAvgValue = sum/len(res['Datapoints'])
            fileName = "/tmp/{}-{}-{}.".format(instance, res['Label'], datetime.now())
            data = {
                'metricName': res['Label'],
                'metricValue': metricAvgValue,
                'instanceId': instance
            }
            create_csv(fileName, data)
            upload_s3(fileName, 'datagrokr-test-dipali', fileName)
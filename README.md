# Unlocking Your Health Score
## Accessing Your Health Score with Webhooks


When SparkPost first released the Health Score in January 2019, it didn’t take long for customers to ask “can I access my Health Score via an API?”.  Some senders wanted to get their Health Score programmatically in order to overlay business metrics in an internal dashboard, or inform projection models.  Some Email Service Providers were interested in using the Health Scores of each of their customers to quickly identify those who needed help, and to automatically organize senders in shared pools.  Then later in 2019, SparkPost launched [Real-Time Alerts](https://www.sparkpost.com/blog/rest-easy-real-time-alerts/) which customers could use to receive notifications of any meaningful changes in specific metrics - including how their Health Score has changed.  By utilizing these alerts, customers have an opportunity to automatically receive their updated Health Scores each day.

This project will explore how you can leverage the SparkPost Real-Time Alerts to get your Health Score programmatically via a webhook.  To do this, we will create an alert in SparkPost that will trigger whenever the Health Scores for each subaccount is greater than 0, which will then send a webhook to an application load balancer within AWS to store the Health Score data for use by downstream applications and processes.

The complete workflow can be described as:
* Create an alert within SparkPost to send a webhook whenever the Health Score for any subaccount is greater than 0
* The alert is triggered each day and sends a webhook payload with the most updated Health Score data for each subaccount. 
* The webhook payload is sent to application load balancer (ALB) within AWS
* The ALB will trigger a Lambda function that validates the data and writes it to an S3 bucket for storage
* The data is loaded into a database and/or data lake for analysis and access to downstream applications

![Flowchart](/img/hs_alert_flowchart.png)


## Create the Alert

Your Health Score is updated daily, and is calculated across a number of facets, including at the overall account level and for each subaccount.  With SparkPost Alerts you can configure a maximum or minimum threshold upon which if the Health Score passes, a notification will be received.  Alerts can be received by a few different methods:  email, Slack, or webhook.  For this example, we will configure our alert to send via webhook.  We will also configure our alert to trigger if the Health Score for any subaccount is greater than 0, which should be the case for any active subaccount.  Each day when the Health Score is updated, SparkPost will check if the alert criteria have been met, and will send a webhook payload containing the Health Score which triggered the alert.  SparkPost Alerts will only trigger once every 24 hours, which is perfect because your Health Score is only updated once per day.  With these configurations, we will receive a webhook payload every day that contains the updated Health Score for each active subaccount.

## Receive and Store the Data

### Create an Application Load Balancer

In order to receive an alert via webhook, we need to provide an endpoint to send the payloads to.  We could implement a number of different solutions to accept the webhook payload, such as an HTTP Gateway or connecting directly to an application load balancer (ALB).  I chose to use an ALB for this project because it is more lightweight and cost-effective than HTTP Gateway; although there is additional functionality within the HTTP Gateway that may be useful - such as request and response mapping.  It’s important to note that if you choose to use an HTTP Gateway, the event format will be different than with an application load balancer, and therefore your Lambda function will need to handle the request object accordingly.

### Add an A Record in DNS that Points to the ALB

To make it easier for us to use our ALB as an endpoint, we will create an A record in DNS that points to our ALB.  I did this by creating the A record hsalert.trymsys.net, which points to the ALB I created.  At this point, we also need to make sure our SparkPost alert is updated to send the webhook payload to this endpoint.

### Create a Lambda Function

Now that we are able to successfully send a SparkPost alert to our ALB, we need a way to accept the payload and process it for downstream applications.  To do this, we will create a Lambda function, which is a serverless compute service that runs when triggered by an event.  In our case, the Lambda function will accept and verify the webhook payload, and then store the information by writing as a file to an S3 bucket, as well as writing to a database (discussed in more detail later).  

The Lambda function created for this project is relatively simple.  First, it loads the body of the payload into an array, enabling the Lambda to iterate through each of the subaccounts, and convert the body into a class which makes it easier to handle the nested objects.  This has the added benefit of validating the format of the body.  Once the body has been converted into a class, the data is written to a file on S3 as well as writing the data to a database - more on this in the section below.  I used the naming convention "HS-subaccount_id-datetime" to make it easier to identify.  It’s important to note that your Lambda execution role will require “PutObject” permissions to write a file to S3.
  
I should also note that I adjusted the Lambda settings to make the timeout 10 seconds, as the default is 3 seconds.  As mentioned above, SparkPost does not automatically retry the webhooks at the time of writing, so this should be considered when setting the Lambda timeout interval.  This is especially true for customers with large numbers of subaccounts, for which the size of the payloads will grow proportionally.  For this project I am only receiving data for about 5-10 subaccounts each day, so a timeout of 10 seconds gives my Lambda function plenty of time to finish.

You can find the Lambda function that I created for this project stored as "receive-webhook-lambda.py".

## Load the Data for Internal Use

At this point, we are storing the Health Score data in S3, which is great for simple storage; however, you will likely want to load this data into a database or data lake so that internal applications can access the data for automation and analysis.  For this project, I chose to support both of these use cases by creating a data lake from the files in S3, as well as writing to a DynamoDB table.

### Create Data Lake
Data lakes are great for processing large volumes of data, as well as processing unstructured data, and are useful when performing analysis or data modeling.  If you already have a data lake that you have implemented, the Health Score data can be included as another table, or you can create a new data lake.  For this project, I created a new data lake using AWS Lake Formation.

The first step is to register the S3 bucket, which instructs Lake Formation of which S3 locations to access.  Then I created the database and used AWS Glue with a crawler to create the schema and database table from the files on S3.  The crawler will go through the files in a folder on S3 and identify the fields and data types within those files to define a schema for your data lake.   Another great thing about the data lake is that as new files are added to the S3 bucket, the Health Score data will automatically get loaded into our data lake.  Once the crawler has finished and the data lake has been created, you can use Athena to query the table and view the respective Health Score for each subaccount.

### Access Data via DynamoDB

In addition to loading the Health Score data into a data lake, you may also want to load the data into database services so that downstream and internal applications can access the latest Health Score data on-demand.  There are several database solutions that can be used, such as RDS, DynamoDB, and others.  Depending on your environment and use case, you may even have multiple locations where this data should be uploaded to.  

For this project, I wrote the data to a DynamoDB table in the same Lambda function where the files are saved to S3, so that the data is available in both locations at the same time.  I chose DynamoDB for ease of use because the payload data is delivered as JSON with nested objects, and DynamoDB is a non-relational database that does not require a schema to be defined.  

Something to be mindful of is scalability - as the size of the payloads increase, so too will the processing time required by the Lambda function.  For this project I am only receiving data for about 5-10 subaccounts, so given the small number of subaccounts for which I am receiving Health Score data, and the quick write time to DynamoDB, I felt comfortable loading this data synchronously within the same Lambda function; however, a more scalable solution to support greater numbers of subaccounts might be to split the functionality into two separate Lambda functions: one that stores the data to S3, and a second that is triggered by the create event on S3 and loads the data to DynamoDB asynchronously.

To implement DynamoDB, the first step was to create a table.  Since DynamoDB does not require a schema to be pre-defined, we can simply add new items to the table and define the schema within our Lambda function.  DynamoDB does, however, require a primary key to be set when creating the table.  The payload that is sent by SparkPost does not include an inherent unique identifier, so I approached this by creating a new field within the Lambda function called “record_id”, and populated it with a UUID.  The field “record_id” was then used as the primary key for my table.

The remainder of the schema for the items is mapped out in the Lambda function before writing to DynamoDB.  I used Boto3 to manage the connection with DynamoDB.  While the schema does not have to be defined in advance, the data types do need to be defined when writing a new item to the table with Boto3.  I also chose to format the Health Score to round to three decimal places for easier management - this is just a personal preference.

Make sure your Lambda execution role has “PutItem” permissions to write new records into DynamoDB!

## Conclusion

Now you are receiving the Health Score for each of your subaccounts each day from the webhooks, and the data is loading into your database and/or data lake.  Your downstream applications and processes can now access the Health Score internally.  You have successfully unlocked your Health Score for use in a broader context.   

One important factor to consider is your retention period.  For long-term analysis and modeling, you may want to store your Health Score data for an extended period of time; whereas for applications that only require the current Health Score to drive automated processes, a retention period of a day or two may be sufficient.

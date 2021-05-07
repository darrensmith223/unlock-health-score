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

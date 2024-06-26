output "apigat_execution_arn" {
  value = aws_api_gateway_rest_api.api.execution_arn
}

output "invoke_url_apigate" {
  description = "URL API Lambda"
  value = aws_api_gateway_deployment.deployment.invoke_url
}
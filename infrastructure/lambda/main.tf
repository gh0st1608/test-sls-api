#provider "archive" {}

data "archive_file" "lambda" {
  type        = "zip"
  source_file = "lambda_function.py"
  output_path = "test.zip"
}

data "aws_iam_policy_document" "AWSLambdaTrustPolicy" {
  version = "2012-10-17"
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

/* data "aws_iam_policy_document" "AWSEc2TrustPolicy" {
  version = "2012-10-17"
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
} */



resource "aws_iam_role" "iam_role" {
  assume_role_policy = data.aws_iam_policy_document.AWSLambdaTrustPolicy.json
  name               = "lambda-iam-role-lambda-trigger"
}

resource "aws_iam_role_policy_attachment" "iam_role_policy_attachment_lambda_basic_execution" {
  /* for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEC2FullAccess", 
    "arn:aws:iam::aws:policy/AmazonS3FullAccess"
  ]) */
  role       = aws_iam_role.iam_role.name
  #policy_arn = each.value
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaENIManagementAccess"
}

resource "aws_lambda_function" "lambda_function" {
  #depends_on = ["aws_iam_role_policy_attachment.iam_role_policy_attachment_lambda_basic_execution"]
  code_signing_config_arn = ""
  description             = ""
  #filename                = data.archive_file.lambda.output_path
  filename                = "test.zip"
  function_name           = "similarity"
  role                    = aws_iam_role.iam_role.arn
  handler                 = "lambda_function.lambda_handler"
  runtime                 = "python3.8"
  #source_code_hash        = filebase64sha256(data.archive_file.lambda.output_path)
  source_code_hash        = data.archive_file.lambda.output_base64sha256
  depends_on = [var.efs_mount_target]

  environment {
    variables = {
      DB_HOST = var.secret_host_lamba
      DB_BD = var.secret_bd_lamba
      DB_USER = var.secret_user_lamba
      DB_PASS = var.secret_pass_lamba
      OPENAI_API_KEY = var.open_ai_key
    }
  }

  ephemeral_storage {
    size = 2048 # Min 512 MB and the Max 10240 MB
  }

  file_system_config {
    arn = var.access_point_arn # EFS file system access point ARN
    local_mount_path = "/mnt/efs"  # Local mount path inside the lambda function. Must start with '/mnt/'.
  }

  vpc_config {
    subnet_ids         = [var.subnet_private_id]
    security_group_ids = [var.seg_group_lambda_id]
  }
}

resource "aws_lambda_permission" "apigw_lambda" {
  statement_id = "AllowExecutionFromAPIGateway"
  action = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_function.function_name
  principal = "apigateway.amazonaws.com"

  source_arn = "${var.apigat_execution_arn}/*/*/*"
}
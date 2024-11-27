variable "seg_group_lambda_id" {
   type = string
}

variable "subnet_private_id" {
   type = string
}

variable "subnet_public_id" {
   type = string
}

/* variable "apigat_execution_arn"{
   type = string
} */

variable "access_point_arn" {
  type = string
} 

variable "efs_mount_target" {
}

variable "secret_host_lambda" {
  type = string
}

variable "secret_bd_lambda" {
  type = string
}

variable "secret_user_lambda" {
  type = string
}

variable "secret_pass_lambda" {
  type = string
}

variable "secret_port_lambda" {
  type = number
}

variable "open_ai_key" {
  type = string
}
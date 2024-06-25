/* module "security_group" {
  source = "./sg"
  vpc_id = module.vpc.vpc_id
}*/
module "apigat" {
  source = "./apigat"
  lambda_invoke_arn = module.lambda.lambda_invoke_arn
}

module "key_pair" {
  source = "./keypair"
}

#----------parte1
module "lambda" {
  source = "./lambda"
  subnet_private_id = module.vpc.subnet_private_id
  seg_group_lambda_id = module.vpc.seg_group_lambda_id
  apigat_execution_arn = module.apigat.apigat_execution_arn
  access_point_arn = module.efs.access_point_arn
}

module "vpc" {
    source = "./vpc"
} 
#----------fin parte1

module "efs" {
    source = "./efs"
    seg_group_lambda_id = module.vpc.seg_group_lambda_id
    public_ip = module.ec2.public_ip
    subnet_private_id = module.vpc.subnet_private_id
}


module "ec2" {
  source   = "./ec2"
  key_name = module.key_pair.key_name
  seg_group_lambda_id = module.vpc.seg_group_lambda_id
  subnet_private_id = module.vpc.subnet_private_id
}



resource "aws_instance" "slsserver" {
  ami           = var.ami_id
  instance_type = var.instance_type
  subnet_id = var.subnet_private_id
  vpc_security_group_ids = [var.seg_group_lambda_id]
  key_name = var.key_name
  tags = {
    Name = "server_sls"
  }

}

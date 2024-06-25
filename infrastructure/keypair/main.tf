resource "aws_key_pair" "sls_key" {
  key_name   = var.key_pair_name
  public_key = file("chupetex")
}
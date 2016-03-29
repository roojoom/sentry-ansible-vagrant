require 'yaml'

configs = YAML.load_file(ENV['HOME']+"/Projects/conf/azure-sentry.yml")
pem_file = configs['pem_file'].sub! '~', ENV['HOME']
cer_file = configs['cer_file'].sub! '~', ENV['HOME']

Vagrant.configure(2) do |config|
  config.vm.box = "azure"
  config.ssh.username = configs['user_name']
  config.ssh.private_key_path = pem_file

  config.vm.provider :azure do |azure, override|
    azure.mgmt_certificate = pem_file
    azure.mgmt_endpoint = 'https://management.core.windows.net'
    azure.vm_image = 'b39f27a8b8c64d52b05eac6a62ebad85__Ubuntu-14_04_3-LTS-amd64-server-20150805-en-us-30GB'
    azure.subscription_id = configs['subscription_id']
    azure.cloud_service_name = configs['service_name']
    azure.storage_acct_name = configs['service_name']
    azure.vm_user = configs['user_name']
    azure.vm_password = configs['vm_password']
    azure.vm_name = configs['user_name']
    azure.vm_location = 'East US'
    override.ssh.password = configs['vm_password']
    azure.ssh_private_key_file = pem_file
    azure.tcp_endpoints = '9000:9000,80:80'
  end


end

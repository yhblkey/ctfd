# coding=utf-8
import docker

class Docker_utils(object):
    # 创建并运行新的题目容器
    # 需要设置运行容器的网络 container_network , container_name , image_name
    #
    @staticmethod
    def create_container(container_network, container_name, image_name):
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        client.containers.run(image_name, network=container_network, detach=True, name=container_name)

    @staticmethod
    def remove_container(container_name):
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        container = client.containers.get(container_name)
        container.remove(force=True)

    @staticmethod
    def getIPAdress_container(container_network, container_name):
        client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        container = client.containers.get(container_name)
        container.reload()
        return container.attrs['NetworkSettings']['Networks'][container_network]['IPAddress']



# coding=utf-8
import requests

# mode = digital_port/dynamic_host
class Frpc_utils(object):


    @staticmethod
    def add_frpcRule(container_ip, container_ip_port, remote_info, mode, rule_name, api_adress, api_adress_port):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'close'
        }
        api_url = 'http://' + api_adress + ':' + api_adress_port
        api_url_config = api_url + '/api/config'
        api_url_reload = api_url + '/api/reload'
        # get old  FrpcRule
        request_frpc_rule = requests.request('get', url=api_url_config, headers=headers).text
        # str to list
        frpc_rule_list = request_frpc_rule.split('\n')
        # print frpcRule_list

        # list to str
        # print '\n'.join(frpcRule_list)

        if len(frpc_rule_list) == 0:
            return False

        # create new FrpcRule
        if mode == 'digital_port':
            if not remote_info.isdigit():
                return False
            rule_template = [
                '[' + rule_name + ']',
                'type = tcp',
                'local_ip = ' + container_ip,
                'local_port = ' + container_ip_port,
                'remote_port = ' + remote_info
            ]
            # print rule_template
            frpc_rule_list.extend(rule_template)
            data = '\n'.join(frpc_rule_list)
            r_1 = requests.put(url=api_url_config, data=data, headers=headers).status_code
            r_2 = requests.get(url=api_url_reload, headers=headers).status_code
            if r_1 == 200 and r_2 == 200:
                return True
            elif r_2 == 400:
                return False
            else:
                return False
        elif mode == 'dynamic_host':
            if remote_info.isdigit():
                return False
            if container_ip_port == '80':
                method = 'http'
            elif container_ip_port == '443':
                method = 'https'
            else:
                method = 'http'
            rule_template = [
                '[' + rule_name + ']',
                'type = ' + method,
                'local_ip = ' + container_ip,
                'local_port = ' + container_ip_port,
                'subdomain = ' + remote_info
            ]
            # print rule_template
            frpc_rule_list.extend(rule_template)
            data = '\n'.join(frpc_rule_list)
            r_1 = requests.put(url=api_url_config, data=data, headers=headers).status_code
            r_2 = requests.get(url=api_url_reload, headers=headers).status_code
            if r_1 == 200 and r_2 == 200:
                return True
            elif r_2 == 400:
                return False
            else:
                return False
        else:
            return False

    @staticmethod
    def delete_frpcRule(rule_name, api_adress, api_adress_port):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'close'
        }
        api_url = 'http://' + api_adress + ':' + api_adress_port
        api_url_config = api_url + '/api/config'
        api_url_reload = api_url + '/api/reload'
        # get old  FrpcRule
        request_frpc_rule = requests.request('get', url=api_url_config, headers=headers).text
        # str to list
        frpc_rule_list = request_frpc_rule.split('\n')
        index = frpc_rule_list.index('[' + rule_name + ']')
        del frpc_rule_list[index:index+5]
        data = '\n'.join(frpc_rule_list)
        r_1 = requests.put(url=api_url_config, data=data, headers=headers).status_code
        r_2 = requests.get(url=api_url_reload, headers=headers).status_code
        if r_1 == 200 and r_2 == 200:
            return True
        elif r_2 == 400:
            return False
        else:
            return False
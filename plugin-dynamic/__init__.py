# coding=utf-8
from __future__ import division  # Use floating point for math calculations

import math
import uuid
import json
from datetime import datetime

from flask import Blueprint, render_template, request

from CTFd.models import (
    ChallengeFiles,
    Challenges,
    Fails,
    Flags,
    Hints,
    Solves,
    Tags,
    db,
)
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge
from CTFd.plugins.flags import get_flag_class
from CTFd.utils.modes import get_model
from CTFd.utils.uploads import delete_file
from CTFd.utils.user import get_ip
from CTFd.utils import user as current_user
from CTFd.utils.decorators import admins_only, authed_only
from .dbUtils import DBUtils
from .Docker_utils import Docker_utils
from .Frpc_utils import Frpc_utils




class PulginDynamicChallenge(BaseChallenge):
    id = "plugin-dynamic"  # Unique identifier used to register challenges
    name = "plugin-dynamic"  # Name of a challenge type
    templates = {  # Handlebars templates used for each aspect of challenge editing & viewing
        "create": "/plugins/plugin-dynamic/assets/create.html",
        "update": "/plugins/plugin-dynamic/assets/update.html",
        "view": "/plugins/plugin-dynamic/assets/view.html",
    }
    scripts = {  # Scripts that are loaded when a template is loaded
        "create": "/plugins/plugin-dynamic/assets/create.js",
        "update": "/plugins/plugin-dynamic/assets/update.js",
        "view": "/plugins/plugin-dynamic/assets/view.js",
    }
    # Route at which files are accessible. This must be registered using register_plugin_assets_directory()
    route = "/plugins/plugin-dynamic/assets/"
    # Blueprint used to access the static_folder directory.
    blueprint = Blueprint(
        "plugin-dynamic",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )

    @classmethod
    def calculate_value(cls, challenge):
        Model = get_model()

        solve_count = (
            Solves.query.join(Model, Solves.account_id == Model.id)
            .filter(
                Solves.challenge_id == challenge.id,
                Model.hidden == False,
                Model.banned == False,
            )
            .count()
        )

        # If the solve count is 0 we shouldn't manipulate the solve count to
        # let the math update back to normal
        if solve_count != 0:
            # We subtract -1 to allow the first solver to get max point value
            solve_count -= 1

        # It is important that this calculation takes into account floats.
        # Hence this file uses from __future__ import division
        value = (
            ((challenge.minimum - challenge.initial) / (challenge.decay ** 2))
            * (solve_count ** 2)
        ) + challenge.initial

        value = math.ceil(value)

        if value < challenge.minimum:
            value = challenge.minimum

        challenge.value = value
        db.session.commit()
        return challenge

    @staticmethod
    def create(request):
        """
        This method is used to process the challenge creation request.

        :param request:
        :return:
        """
        data = request.form or request.get_json()
        challenge = DynamicChallengeExc(**data)

        db.session.add(challenge)
        db.session.commit()

        return challenge

    @staticmethod
    def read(challenge):
        """
        This method is in used to access the data of a challenge in a format processable by the front end.

        :param challenge:
        :return: Challenge object, data dictionary to be returned to the user
        """
        challenge = DynamicChallengeExc.query.filter_by(id=challenge.id).first()
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "initial": challenge.initial,
            "decay": challenge.decay,
            "minimum": challenge.minimum,
            "description": challenge.description,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "docker_image": challenge.docker_image,
            "redirect_type": challenge.redirect_type,
            "redirect_port": challenge.redirect_port,
            "type": challenge.type,
            "type_data": {
                "id": PulginDynamicChallenge.id,
                "name": PulginDynamicChallenge.name,
                "templates": PulginDynamicChallenge.templates,
                "scripts": PulginDynamicChallenge.scripts,
            },
        }
        return data

    @staticmethod
    def update(challenge, request):
        """
        This method is used to update the information associated with a challenge. This should be kept strictly to the
        Challenges table and any child tables.

        :param challenge:
        :param request:
        :return:
        """
        data = request.form or request.get_json()

        for attr, value in data.items():
            # We need to set these to floats so that the next operations don't operate on strings
            if attr in ("initial", "minimum", "decay"):
                value = float(value)
            setattr(challenge, attr, value)

        return PulginDynamicChallenge.calculate_value(challenge)

    @staticmethod
    def delete(challenge):
        """
        This method is used to delete the resources used by a challenge.

        :param challenge:
        :return:
        """
        Fails.query.filter_by(challenge_id=challenge.id).delete()
        Solves.query.filter_by(challenge_id=challenge.id).delete()
        Flags.query.filter_by(challenge_id=challenge.id).delete()
        files = ChallengeFiles.query.filter_by(challenge_id=challenge.id).all()
        for f in files:
            delete_file(f.id)
        ChallengeFiles.query.filter_by(challenge_id=challenge.id).delete()
        Tags.query.filter_by(challenge_id=challenge.id).delete()
        Hints.query.filter_by(challenge_id=challenge.id).delete()
        DynamicChallengeExc.query.filter_by(id=challenge.id).delete()
        Challenges.query.filter_by(id=challenge.id).delete()
        db.session.commit()

    @staticmethod
    def attempt(challenge, request):
        """
        This method is used to check whether a given input is right or wrong. It does not make any changes and should
        return a boolean for correctness and a string to be shown to the user. It is also in charge of parsing the
        user's input from the request itself.

        :param challenge: The Challenge object from the database
        :param request: The request the user submitted
        :return: (boolean, string)
        """
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        flags = Flags.query.filter_by(challenge_id=challenge.id).all()
        for flag in flags:
            if get_flag_class(flag.type).compare(flag, submission):
                return True, "Correct"
        return False, "Incorrect"

    @staticmethod
    def solve(user, team, challenge, request):
        """
        This method is used to insert Solves into the database in order to mark a challenge as solved.

        :param team: The Team object from the database
        :param chal: The Challenge object from the database
        :param request: The request the user submitted
        :return:
        """
        challenge = DynamicChallengeExc.query.filter_by(id=challenge.id).first()
        data = request.form or request.get_json()
        submission = data["submission"].strip()

        solve = Solves(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(req=request),
            provided=submission,
        )
        db.session.add(solve)
        db.session.commit()

        PulginDynamicChallenge.calculate_value(challenge)

    @staticmethod
    def fail(user, team, challenge, request):
        """
        This method is used to insert Fails into the database in order to mark an answer incorrect.

        :param team: The Team object from the database
        :param challenge: The Challenge object from the database
        :param request: The request the user submitted
        :return:
        """
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        wrong = Fails(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(request),
            provided=submission,
        )
        db.session.add(wrong)
        db.session.commit()
        db.session.close()


class DynamicChallengeExc(Challenges):
    __mapper_args__ = {"polymorphic_identity": "plugin-dynamic"}
    id = db.Column(None, db.ForeignKey("challenges.id"), primary_key=True)
    initial = db.Column(db.Integer, default=0)
    minimum = db.Column(db.Integer, default=0)
    decay = db.Column(db.Integer, default=0)
    docker_image = db.Column(db.Text, default=0)
    redirect_type = db.Column(db.Text, default=0)
    redirect_port = db.Column(db.Integer, default=0)
    
    def __init__(self, *args, **kwargs):
        super(DynamicChallengeExc, self).__init__(**kwargs)
        self.initial = kwargs["value"]


def load(app):
    # upgrade()
    app.db.create_all()
    CHALLENGE_CLASSES["plugin-dynamic"] = PulginDynamicChallenge
    register_plugin_assets_directory(
        app, base_path="/plugins/plugin-dynamic/assets/"
    )

    page_blueprint = Blueprint(
        "ctfd-dynamic",
        __name__,
        template_folder="templates",
        static_folder="assets",
        url_prefix="/plugins/plugin-dynamic"
    )

    # # 定义映射端口列表
    # port_range = []

    @page_blueprint.route('/settings', methods=['GET'])
    @admins_only
    def plugin_list_configs():
        # configs = DBUtils.get_all_configs()
        # return render_template('test.html', content="<h1>test %s</h1>" % test[1])
        configs = DBUtils.get_all_pluginconfigs()
        return render_template('config.html', configs=configs)

    @page_blueprint.route('/settings', methods=['PATCH'])
    @admins_only
    def plugin_save_configs():
        req = request.get_json()
        DBUtils.save_all_pluginconfigs(req.items())
        # redis_util = RedisUtils(app=app)
        # redis_util.init_redis_port_sets()
        DBUtils.MaxPort = DBUtils.get_all_pluginconfigs().get("server_port_maximum")
        DBUtils.MinPort = DBUtils.get_all_pluginconfigs().get("server_port_minimum")
        DBUtils.port_range = list(range(int(DBUtils.MinPort), int(DBUtils.MaxPort)+1))
        return json.dumps({'success': True})


    @page_blueprint.route('/container', methods=['POST'])
    @authed_only
    def add_container():
        user_id = current_user.get_current_user().id
        req = request.get_json()
        challenge_id = req.get("challenge_id")
        if DBUtils.get_container_by_user(user_id) == None:
            # 首先创建添加容器所需要的元素
            plugin_configs = DBUtils.get_all_pluginconfigs()
            container_network = plugin_configs.get("container_network")
            uuid_code = uuid.uuid4()
            container_name = str(user_id) + "-" + str(uuid_code) 
            docker_image = DynamicChallengeExc.query.filter_by(id=challenge_id).first().docker_image
            container_port = DynamicChallengeExc.query.filter_by(id=challenge_id).first().redirect_port
            mode = DynamicChallengeExc.query.filter_by(id=challenge_id).first().redirect_type
            rule_name = container_name
            api_adress = plugin_configs.get("frpc_api_ip")
            api_port = plugin_configs.get("frpc_api_port")

            # 生成挑战对应的docker容器

            # Docker_utils.create_container(container_network=container_network, container_name=container_name, image_name=docker_image)

            if mode == "digital_port":
                if len(DBUtils.port_range) == 0:
                    
                    return json.dumps({'success': False, 'msg':'Running container reached upper limit'})
                
                remote_info = DBUtils.port_range.pop()

            elif mode == "dynamic_host":
                
                remote_info = container_name

            else:
                return json.dumps({'success': False, 'msg':'This mode does not exist'})
            # 启动容器
            Docker_utils.create_container(container_network=container_network, container_name=container_name, image_name=docker_image)
            # 将启动的容器信息存入数据库ChallengeContainerV2
            DBUtils.create_new_container(user_id=user_id, challenge_id=challenge_id, uuid=uuid_code, remote_info=str(remote_info))
            # 获取启动成功的容器IP
            container_ip = Docker_utils.getIPAdress_container(container_network=container_network, container_name=container_name)
            # 设置Frp的映射规则
            Frpc_utils.add_frpcRule(container_ip=container_ip, container_ip_port=str(container_port), remote_info=str(remote_info), mode=mode, rule_name=container_name, api_adress=api_adress, api_adress_port=str(api_port))

            return json.dumps({'success': True})

        else:
            return json.dumps({'success': False, 'msg': 'You have created a container. If you want to create a new container, first destroy the old container.'})


    @page_blueprint.route('/container', methods=['GET'])
    @authed_only
    def get_containerinfo():
        user_id = current_user.get_current_user().id
        challenge_id = request.args.get('challenge_id')
        mode = DynamicChallengeExc.query.filter_by(id=challenge_id).first().redirect_type
        challenge_info = DBUtils.get_current_containers(user_id, challenge_id)
        plugin_configs = DBUtils.get_all_pluginconfigs()

        if challenge_info == None:

            return json.dumps({'success': False,'msg':'Container has not been created by the current user'})

        if mode == "digital_port":
            remote_port = challenge_info.remote_info
            server_ip = plugin_configs.get("server_ip")
            return json.dumps({'success': True, 'server_ip': server_ip, 'remote_port': remote_port, 'type':mode})
        elif mode == "dynamic_host":
            subdomain = challenge_info.remote_info
            server_domain = plugin_configs.get("server_domain")
            return json.dumps({'success': True, 'server_domain': server_domain, 'subdomain': subdomain, 'type':mode})
        else:
            return json.dumps({'success': False, 'msg':'This mode does not exist'})


    @page_blueprint.route('/container-dele', methods=['GET'])
    @authed_only
    def dele_container():
        user_id = current_user.get_current_user().id
        challenge_id = request.args.get('challenge_id')
        challenge_info = DBUtils.get_container_by_user(user_id)
        if challenge_info == None:
            return json.dumps({'success': False,'msg':'Container has not been created by the current user'})
        mode = DynamicChallengeExc.query.filter_by(id=challenge_id).first().redirect_type
        if mode == "digital_port":
            if int(challenge_info.remote_info) >= int(DBUtils.MinPort) and int(challenge_info.remote_info) <= int(DBUtils.MaxPort):
                DBUtils.port_range.append(int(challenge_info.remote_info))
        # 删除当前用户创建的容器
        container_name = str(challenge_info.user_id) + "-" + str(challenge_info.uuid)
        Docker_utils.remove_container(container_name)
        # 删除当前用户创建的容器的映射规则
        plugin_configs = DBUtils.get_all_pluginconfigs()
        api_adress = plugin_configs.get("frpc_api_ip")
        api_port = plugin_configs.get("frpc_api_port")
        Frpc_utils.delete_frpcRule(rule_name= container_name, api_adress=api_adress, api_adress_port=api_port)
        # 删除当前数据库中的数据
        DBUtils.remove_current_container(user_id)
        return json.dumps({'success': True, 'msg':'deleted'})

    @page_blueprint.route('/container-reload', methods=['POST'])
    @authed_only
    def reload_container():
        user_id = current_user.get_current_user().id
        req = request.get_json()
        challenge_id = req.get("challenge_id")
        # 首先删除当前用户创建的容器
        challenge_info = DBUtils.get_container_by_user(user_id)
        if challenge_info == None:
            return json.dumps({'success': False,'msg':'Container has not been created by the current user'})
        mode = DynamicChallengeExc.query.filter_by(id=challenge_id).first().redirect_type

        if mode == "digital_port":
            if int(challenge_info.remote_info) >= int(DBUtils.MinPort) and int(challenge_info.remote_info) <= int(DBUtils.MaxPort):
                DBUtils.port_range.append(int(challenge_info.remote_info))

        # 删除当前用户创建的容器
        container_name = str(challenge_info.user_id) + "-" + str(challenge_info.uuid)
        Docker_utils.remove_container(container_name)
        # 删除当前用户创建的容器的映射规则
        plugin_configs = DBUtils.get_all_pluginconfigs()
        api_adress = plugin_configs.get("frpc_api_ip")
        api_port = plugin_configs.get("frpc_api_port")
        Frpc_utils.delete_frpcRule(rule_name= container_name, api_adress=api_adress, api_adress_port=api_port)
        # 删除当前数据库中的数据
        DBUtils.remove_current_container(user_id)

        # 开始创建新的容器
        if DBUtils.get_container_by_user(user_id) == None:
            # 首先创建添加容器所需要的元素
            container_network = plugin_configs.get("container_network")
            uuid_code = uuid.uuid4()
            container_name = str(user_id) + "-" + str(uuid_code) 
            docker_image = DynamicChallengeExc.query.filter_by(id=challenge_id).first().docker_image
            container_port = DynamicChallengeExc.query.filter_by(id=challenge_id).first().redirect_port
            rule_name = container_name

            # 生成挑战对应的docker容器
            # Docker_utils.create_container(container_network=container_network, container_name=container_name, image_name=docker_image)

            if mode == "digital_port":
                if len(DBUtils.port_range) == 0:
                    
                    return json.dumps({'success': False, 'msg':'Running container reached upper limit'})
                
                remote_info = DBUtils.port_range.pop()

            elif mode == "dynamic_host":
                
                remote_info = container_name

            else:
                return json.dumps({'success': False, 'msg':'This mode does not exist'})
            # 启动容器
            Docker_utils.create_container(container_network=container_network, container_name=container_name, image_name=docker_image)
            # 将启动的容器信息存入数据库ChallengeContainerV2
            DBUtils.create_new_container(user_id=user_id, challenge_id=challenge_id, uuid=uuid_code, remote_info=str(remote_info))
            # 获取启动成功的容器IP
            container_ip = Docker_utils.getIPAdress_container(container_network=container_network, container_name=container_name)
            # 设置Frp的映射规则
            Frpc_utils.add_frpcRule(container_ip=container_ip, container_ip_port=str(container_port), remote_info=str(remote_info), mode=mode, rule_name=container_name, api_adress=api_adress, api_adress_port=str(api_port))

            return json.dumps({'success': True})


        else:
            return json.dumps({'success': False, 'msg': 'You have created a container. If you want to create a new container, first destroy the old container.'})


    @page_blueprint.route("/admin/containers-dele", methods=['GET'])
    @admins_only
    def admin_dele_containers():

        user_id = request.args.get('user_id')
        challenge_info = DBUtils.get_container_by_user(user_id)
        challenge_id = challenge_info.challenge_id
        if challenge_info == None:
            return json.dumps({'success': False,'msg':'Container has not been created by the current user'})
        mode = DynamicChallengeExc.query.filter_by(id=challenge_id).first().redirect_type
        if mode == "digital_port":
            if int(challenge_info.remote_info) >= int(DBUtils.MinPort) and int(challenge_info.remote_info) <= int(DBUtils.MaxPort):
                DBUtils.port_range.append(int(challenge_info.remote_info))
        # 删除当前用户创建的容器
        container_name = str(challenge_info.user_id) + "-" + str(challenge_info.uuid)
        Docker_utils.remove_container(container_name)
        # 删除当前用户创建的容器的映射规则
        plugin_configs = DBUtils.get_all_pluginconfigs()
        api_adress = plugin_configs.get("frpc_api_ip")
        api_port = plugin_configs.get("frpc_api_port")
        Frpc_utils.delete_frpcRule(rule_name= container_name, api_adress=api_adress, api_adress_port=api_port)
        # 删除当前数据库中的数据
        DBUtils.remove_current_container(user_id)
        return json.dumps({'success': True, 'msg':'deleted'})

    @page_blueprint.route("/admin/containers", methods=['GET'])
    @admins_only
    def admin_list_containers():

        page = abs(request.args.get("page", 1, type=int))
        results_per_page = 10
        page_start = results_per_page * (page - 1)
        page_end = results_per_page * (page - 1) + results_per_page

        count = DBUtils.get_all_alive_container_count()
        containers = DBUtils.get_all_alive_container_page(page_start, page_end)
        pages = int(count / results_per_page) + int(count % results_per_page > 0)
        return render_template("containers.html", containers=containers, pages=pages, curr_page=page, curr_page_start=page_start)

    app.register_blueprint(page_blueprint)










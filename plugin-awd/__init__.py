# coding=utf-8
from __future__ import division  # Use floating point for math calculations

import math
import uuid
import json
from datetime import datetime
import requests

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



class PulginAwdChallenge(BaseChallenge):
    id = "plugin-awd"  # Unique identifier used to register challenges
    name = "plugin-awd"  # Name of a challenge type
    templates = {  # Handlebars templates used for each aspect of challenge editing & viewing
        "create": "/plugins/plugin-awd/assets/create.html",
        "update": "/plugins/plugin-awd/assets/update.html",
        "view": "/plugins/plugin-awd/assets/view.html",
    }
    scripts = {  # Scripts that are loaded when a template is loaded
        "create": "/plugins/plugin-awd/assets/create.js",
        "update": "/plugins/plugin-awd/assets/update.js",
        "view": "/plugins/plugin-awd/assets/view.js",
    }
    # Route at which files are accessible. This must be registered using register_plugin_assets_directory()
    route = "/plugins/plugin-awd/assets/"
    # Blueprint used to access the static_folder directory.
    blueprint = Blueprint(
        "plugin-awd",
        __name__,
        template_folder="templates",
        static_folder="assets",
    )


    @staticmethod
    def create(request):
        """
        This method is used to process the challenge creation request.

        :param request:
        :return:
        """
        data = request.form or request.get_json()
        challenge = AwdChallengeExc(**data)

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
        challenge = AwdChallengeExc.query.filter_by(id=challenge.id).first()
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "description": challenge.description,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "url": challenge.flag_submission,
            "type_data": {
                "id": PulginAwdChallenge.id,
                "name": PulginAwdChallenge.name,
                "templates": PulginAwdChallenge.templates,
                "scripts": PulginAwdChallenge.scripts,
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
            setattr(challenge, attr, value)

        db.session.commit()
        return challenge

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
        AwdChallengeExc.query.filter_by(id=challenge.id).delete()
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
        challenge = AwdChallengeExc.query.filter_by(id=challenge.id).first()
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


class AwdChallengeExc(Challenges):
    __mapper_args__ = {"polymorphic_identity": "plugin-awd"}
    id = db.Column(None, db.ForeignKey("challenges.id"), primary_key=True)
    flag_submission = db.Column(db.Text, default=0)

    def __init__(self, *args, **kwargs):
        super(AwdChallengeExc, self).__init__(**kwargs)
        


def load(app):
    # upgrade()
    app.db.create_all()
    CHALLENGE_CLASSES["plugin-awd"] = PulginAwdChallenge
    register_plugin_assets_directory(
        app, base_path="/plugins/plugin-awd/assets/"
    )

    # page_blueprint = Blueprint(
    #     "ctfd-dynamic",
    #     __name__,
    #     template_folder="templates",
    #     static_folder="assets",
    #     url_prefix="/plugins/plugin-dynamic"
    # )

    # # 定义映射端口列表
    # port_range = []

    @app.route('/flag-submission', methods=['POST'])
    @authed_only
    def flag_submission():
        req = request.get_json()
        challenge_id = req.get("challenge_id")
        team = req.get("submission_team")
        flag = req.get("submission_flag")
        url = AwdChallengeExc.query.filter_by(id=challenge_id).first().flag_submission
        url = url + "?token=" + team.strip() + "&flag=" + flag.strip()
        flag_request = requests.request('get', url, headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit'})

        if flag_request.status_code == 200:
            if flag_request.text.find('success') != -1:
                return json.dumps({'success': True})
            else:
                msg = flag_request.text
                return json.dumps({'success': False, 'msg': msg})

        return json.dumps({'success': False, 'msg': 'There is a problem with the address you set for submitting the flag. Please check and reset itself.'})


   









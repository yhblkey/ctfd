from __future__ import division  # Use floating point for math calculations
from datetime import datetime
import math

from flask import Blueprint

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

from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge
from CTFd.plugins.flags import get_flag_class
from CTFd.utils.modes import get_model
from CTFd.utils.uploads import delete_file
from CTFd.utils.user import get_ip



# add 
class PluginConfigV2(db.Model):
    key = db.Column(db.String(length=128), primary_key=True)
    value = db.Column(db.Text)

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __repr__(self):
        return "<PluginConfig (0) {1}>".format(self.key, self.value)

class ChallengeContainerV2(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(None, db.ForeignKey("users.id"))
    challenge_id = db.Column(None, db.ForeignKey("challenges.id"))
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.now())
    uuid = db.Column(db.String(256))
    remote_info = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship("Users", foreign_keys="ChallengeContainerV2.user_id", lazy="select")
    challenge = db.relationship(
        "Challenges", foreign_keys="ChallengeContainerV2.challenge_id", lazy="select"
    )

    def __init__(self, user_id, challenge_id, uuid, remote_info):
        self.user_id = user_id
        self.challenge_id = challenge_id
        self.start_time = datetime.now()
        self.uuid = str(uuid)
        self.remote_info = remote_info

    def __repr__(self):
        return "<ChallengeContainerV2 ID:(0) {1} {2} {3} {4} {5}>".format(self.id, self.user_id, self.challenge_id, self.start_time, self.uuid, self.remote_info)




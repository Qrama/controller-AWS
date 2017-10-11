# !/usr/bin/env python3
# Copyright (C) 2017  Qrama
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# pylint: disable=c0111,c0301,c0325, r0903,w0406
from subprocess import check_output, check_call
from sojobo_api.api import w_errors as errors
from flask import abort
import json
import yaml
from juju.client.connection import JujuData


CRED_KEYS = ['access-key', 'secret-key']


class Token(object):
    def __init__(self, url, username, password):
        self.type = 'aws'
        self.supportlxd = False
        self.url = url


def create_controller(name, region, credentials, cred_name):
    path = create_credentials_file(cred_name, credentials)
    check_call(['juju', 'add-credential', 'aws', '-f', path, '--replace'])
    output = check_output(['juju', 'bootstrap', '--agent-version=2.2.2', 'aws/{}'.format(region), cred_name, '--credential', name])
    return output


def get_supported_series():
    return ['precise', 'trusty', 'xenial', 'yakkety']

def get_supported_regions():
    return ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'ca-central-1',
            'eu-west-1', 'eu-west-2', 'eu-central-1', 'ap-south-1', 'ap-southeast-1',
            'ap-southeast-2', 'ap-northeast-1', 'ap-northeast-2', 'sa-east-1']

def create_credentials_file(name, credentials):
    if len(CRED_KEYS) == len(list(credentials.keys())):
        for cred in CRED_KEYS:
            if not cred in list(credentials.keys()):
                error = errors.key_does_not_exist(cred)
                abort(error[0], error[1])
    path = '/tmp/credentials.yaml'
    data = {'credentials': {'aws': {name: {'auth-type': 'access-key',
                                           'access-key': credentials['access-key'],
                                           'secret-key': credentials['secret-key']}}}}
    with open(path, 'w') as dest:
        yaml.dump(data, dest, default_flow_style=True)
    return path


def generate_cred_file(name, credentials):
    result = {
        'type': 'access-key',
        'name': name,
        'key': json.dumps({'access-key': credentials['access-key'], 'secret-key': credentials['secret-key']})
    }
    return result


# Currently not being used, but already provided if we encounter a cloud which requires some
# specific logic to return this data
def get_public_url(c_name):
    jujudata = JujuData()
    result = jujudata.controllers()
    return result[c_name]['api-endpoints'][0]


# Currently not being used, but already provided if we encounter a cloud which requires some
# specific logic to return this data
def get_gui_url(controller, model):
    return 'https://{}/gui/{}'.format(controller.public_ip, model.m_uuid)

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
from subprocess import check_output, check_call, CalledProcessError
from sojobo_api.api import w_errors as errors
from flask import abort
import yaml
from juju.client.connection import JujuData

CRED_KEYS = ['access-key', 'secret-key']

class Token(object):
    def __init__(self, url, username, password):
        self.type = 'aws'
        self.supportlxd = False
        self.url = url


def create_controller(name, region, credentials):
    path = create_credentials_file(name, credentials)
    check_call(['juju', 'add-credential', 'aws', '-f', path, '--replace'])
    output = check_output(['juju', 'bootstrap', '--agent-version=2.1.2', 'aws/{}'.format(region), name, '--credential', name])
    return output


def get_supported_series():
    return ['precise', 'trusty', 'xenial', 'yakkety']


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

def get_public_url(c_name):
    jujudata = JujuData()
    result = jujudata.controllers()
    return result[c_name]['api-endpoints'][0]


def get_gui_url(controller, model):
    return 'https://{}/gui/{}'.format(controller.public_ip, model.m_uuid)

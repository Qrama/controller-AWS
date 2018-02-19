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
# pylint: disable=c0111,c0301,c0325,c0103,r0913,r0902,e0401,C0302, R0914
import asyncio
import logging
import os
import hashlib
from pathlib import Path
from subprocess import check_output, check_call
import traceback
import sys
import yaml
import json
from juju import tag
from juju.client import client
sys.path.append('/opt')
from sojobo_api import settings  #pylint: disable=C0413
from sojobo_api.api import w_datastore as datastore, w_juju as juju  #pylint: disable=C0413


class JuJu_Token(object):  #pylint: disable=R0903
    def __init__(self):
        self.username = settings.JUJU_ADMIN_USER
        self.password = settings.JUJU_ADMIN_PASSWORD
        self.is_admin = True


async def bootstrap_google_controller(name, region, cred_name):#pylint: disable=E0001
    try:
        token = JuJu_Token()
        logger.info(cred_name)
        valid_cred_name = 't{}'.format(hashlib.md5(cred_name.encode('utf')).hexdigest())
        credential = juju.get_credential(token.username, cred_name)
        logger.info(credential)
        if not credential['state'] == 'ready':
            raise Exception('The Credential {} is not ready yet.'.format(credential['name']))
        juju.get_controller_types()['aws'].check_valid_credentials(credential['credential'])
        cred_path = '/home/{}/credentials'.format(settings.SOJOBO_USER)
        if not os.path.exists(cred_path):
            os.mkdir(cred_path)
        filepath = '{}/aws-{}.json'.format(cred_path, valid_cred_name)
        with open(filepath, 'w+') as credfile:
            json.dump(credential['credential'], credfile)
        path = '/tmp/credentials.yaml'
        data = {'credentials': {'aws': {valid_cred_name: {'auth-type': 'access-key',
                                               'access-key': credential['credential']['access-key'],
                                               'secret-key': credential['credential']['secret-key']}}}}
        with open(path, 'w') as dest:
            yaml.dump(data, dest, default_flow_style=True)
        logger.info(valid_cred_name)
        logger.info(data)
        check_call(['juju', 'add-credential', 'aws', '-f', path, '--replace'])
        logger.info(path)
        check_call(['juju', 'bootstrap', '--agent-version=2.3.0', 'aws/{}'.format(region), name, '--credential', valid_cred_name])
        os.remove(path)

        logger.info('Setting admin password')
        check_output(['juju', 'change-user-password', 'admin', '-c', name],
                     input=bytes('{}\n{}\n'.format(token.password, token.password), 'utf-8'))

        logger.info('Updating controller in database')
        with open(os.path.join(str(Path.home()), '.local', 'share', 'juju', 'controllers.yaml'), 'r') as data:
            con_data = yaml.load(data)
        datastore.set_controller_state(
            name,
            'ready',
            con_data['controllers'][name]['api-endpoints'],
            con_data['controllers'][name]['uuid'],
            con_data['controllers'][name]['ca-cert'])

        logger.info('Connecting to controller')
        controller = juju.Controller_Connection(token, name)

        logger.info('Adding existing credentials and default models to database')
        credentials = datastore.get_credentials(token.username)
        async with controller.connect(token) as juju_con:
            for cred in credentials:
                if cred['name'] != cred_name:
                    await juju.update_cloud(juju_con, cred['name'], token.username)
            models = await juju_con.get_models()
            for model in models.serialize()['user-models']:
                model = model.serialize()['model'].serialize()
                # TODO: Checken of model al bestaat?
                new_model = datastore.create_model(model['name'], state='Model is being deployed', uuid='')
                datastore.add_model_to_controller(name, new_model["_key"])
                datastore.set_model_state(new_model["_key"], 'ready', credential=cred_name, uuid=model['uuid'])
                datastore.set_model_access(new_model["_key"], token.username, 'admin')
        logger.info('Controller succesfully created!')
    except Exception:  #pylint: disable=W0703
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        for l in lines:
            logger.error(l)
        datastore.set_controller_state(name, 'error')


if __name__ == '__main__':
    logger = logging.getLogger('bootstrap_aws_controller')
    hdlr = logging.FileHandler('{}/log/bootstrap_aws_controller.log'.format(settings.SOJOBO_API_DIR))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.INFO)
    loop = asyncio.get_event_loop()
    loop.set_debug(False)
    loop.run_until_complete(bootstrap_google_controller(sys.argv[1], sys.argv[2],
                                              sys.argv[3]))
    loop.close()

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
from juju.controller import Controller
sys.path.append('/opt')
from sojobo_api import settings  #pylint: disable=C0413
from sojobo_api.api import w_datastore as datastore, w_juju as juju  #pylint: disable=C0413


async def bootstrap_aws_controller(c_name, region, cred_name, username, password):#pylint: disable=E0001
    try:
        # Check if the credential is valid.
        tengu_username = settings.JUJU_ADMIN_USER
        tengu_password = settings.JUJU_ADMIN_PASSWORD
        valid_cred_name = 't{}'.format(hashlib.md5(cred_name.encode('utf')).hexdigest())
        credential = juju.get_credential(username, cred_name)
        logger.info(credential)

        juju.get_controller_types()['aws'].check_valid_credentials(credential)

        # Create credential file that can be used to bootstrap controller.
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
        check_call(['juju', 'bootstrap', '--agent-version=2.3.0', 'aws/{}'.format(region), c_name, '--credential', valid_cred_name])
        os.remove(path)

        logger.info('Setting admin password')
        check_output(['juju', 'change-user-password', 'admin', '-c', c_name],
                     input=bytes('{}\n{}\n'.format(tengu_password, tengu_password), 'utf-8'))

        con_data = {}
        logger.info('Updating controller in database')
        with open(os.path.join(str(Path.home()), '.local', 'share', 'juju', 'controllers.yaml'), 'r') as data:
            con_data = yaml.load(data)
        datastore.set_controller_state(
            c_name,
            'ready',
            endpoints=con_data['controllers'][c_name]['api-endpoints'],
            uuid=con_data['controllers'][c_name]['uuid'],
            ca_cert=con_data['controllers'][c_name]['ca-cert'])

        logger.info('Connecting to controller')
        controller = Controller()

        logger.info('Adding existing credentials and default models to database...')
        credentials = datastore.get_cloud_credentials('aws', username)
        logger.info(credentials)
        await controller.connect(endpoint=con_data['controllers'][c_name]['api-endpoints'][0],
                                 username=tengu_username, password=tengu_password,
                                 cacert=con_data['controllers'][c_name]['ca-cert'])
        user_info = datastore.get_user(username)
        juju_username = user_info["juju_username"]
        for cred in credentials:
                if username != tengu_username:
                    await juju.update_cloud(controller, 'aws', cred['name'], juju_username, username)
                    logger.info('Added credential %s to controller %s', cred['name'], c_name)
                elif cred['name'] != cred_name:
                    await juju.update_cloud(controller, 'aws', cred['name'], juju_username, username)
        user = tag.user(juju_username)
        model_facade = client.ModelManagerFacade.from_connection(
                        controller.connection)
        controller_facade = client.ControllerFacade.from_connection(controller.connection)
        if username != tengu_username:
            user_facade = client.UserManagerFacade.from_connection(controller.connection)
            users = [client.AddUser(display_name=juju_username,
                                    username=juju_username,
                                    password=password)]
            await user_facade.AddUser(users)
            changes = client.ModifyControllerAccess('superuser', 'grant', user)
            await controller_facade.ModifyControllerAccess([changes])

        c_info = datastore.get_controller(c_name)
        models = await controller_facade.AllModels()
        for model in models.user_models:
            if model:
                m_key = juju.construct_model_key(c_info['name'], model.model.name)
                logger.info(model.model.name)
                if username != tengu_username:
                    model_tag = tag.model(model.model.uuid)
                    changes = client.ModifyModelAccess('admin', 'grant', model_tag, user)
                    await model_facade.ModifyModelAccess([changes])
                datastore.create_model(m_key, model.model.name, state='Model is being deployed', uuid='')
                datastore.add_model_to_controller(c_name, m_key)
                datastore.set_model_state(m_key, 'ready', credential=cred_name, uuid=model.model.uuid)
                datastore.set_model_access(m_key, username, 'admin')
                ssh_keys = user_info["ssh_keys"]
                if len(ssh_keys) > 0:
                    juju.update_ssh_keys_model(username, ssh_keys, c_name, m_key)
        logger.info('Controller succesfully created!')
    except Exception:  #pylint: disable=W0703
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        for l in lines:
            logger.error(l)
        datastore.set_controller_state(c_name, 'error')
    finally:
        if 'controller' in locals():
            await juju.disconnect(controller)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('bootstrap_aws_controller')
    ws_logger = logging.getLogger('websockets.protocol')
    hdlr = logging.FileHandler('{}/log/bootstrap_aws_controller.log'.format(settings.SOJOBO_API_DIR))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    ws_logger.addHandler(hdlr)
    ws_logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.set_debug(False)
    loop.run_until_complete(bootstrap_aws_controller(sys.argv[1], sys.argv[2],
                                              sys.argv[3], sys.argv[4], sys.argv[5]))
    loop.close()

import json
import os

from flask import Flask, make_response
from mcstatus import JavaServer

import version

app = Flask(__name__)

counter = 0

_json_path = os.getenv('MC_SERVER_JSON', 'server.json')
with open(_json_path, 'r') as _f:
    _config = json.load(_f)
server_list = [str(s) for s in _config.get('servers', [])]


@app.route('/')
def root():
    global counter
    ans = f'Version: {version.version}. Counter: {counter}. Minecraft Server List {server_list}'
    counter += 1
    return ans


@app.route('/metrics')
def metrics():
    global counter
    ans = ''
    for server_name in server_list:
        server = JavaServer.lookup(address=server_name, timeout=0.5)
        try:
            s = server.status()
        except ConnectionRefusedError as e:
            print(f'Minecraft server error: {e}')
            ans += 'server_online{server_name="%s"} %s\n' % (server_name, 0)
        except TimeoutError as e:
            print(f'Minecraft server error: {e}')
            ans += 'server_online{server_name="%s"} %s\n' % (server_name, 0)
        else:
            ans += 'server_online{server_name="%s"} %s\n' % (server_name, 1)
            # since JavaStatusResponse is different for Minecraft Forge Servers we need a hack to get the description
            if s.raw.get('forgeData'):
                description = s.raw['description'].get('text')
            else:
                description = s.description
            ans += 'minecraft_latency{server="%s"} %f\n' % (description, s.latency)
            ans += 'minecraft_version{server="%s", version="%s"} %i\n' % (description, s.version.name, 1)
            ans += 'minecraft_users_max{server="%s"} %i\n' % (description, s.players.max)
            ans += 'minecraft_users_online{server="%s"} %i\n' % (description, s.players.online)
            if s.players.sample:
                for player in s.players.sample:
                    ans += 'minecraft_players{server="%s", name="%s", uuid="%s"} 1\n' % (description, player.name, player.uuid)
    ans += 'minecraft_mcs_count{version="%s"} %s\n' % (version.version, counter)
    counter += 1
    response = make_response(ans, 200)
    response.mimetype = "text/plain"
    return response


if __name__ == '__main__':
    app.run()

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


def _create_version_module():
    """Erstellt ein minimales version-Mock-Modul, falls es nicht existiert."""
    import types
    mod = types.ModuleType('version')
    mod.version = '0.0.0-test'
    mod.commit = 'abc123'
    mod.commit_short = 'abc123'
    sys.modules.setdefault('version', mod)


class TestRoot(unittest.TestCase):
    def setUp(self):
        _create_version_module()
        self._tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump({'servers': ['localhost:25565']}, self._tmp)
        self._tmp.close()
        os.environ['MC_SERVER_JSON'] = self._tmp.name

        # Entferne gecachtes mcsmons-Modul, damit setUp-Env greift
        sys.modules.pop('mcsmons', None)

    def tearDown(self):
        os.unlink(self._tmp.name)
        sys.modules.pop('mcsmons', None)

    def test_root_returns_version_and_counter(self):
        import mcsmons
        client = mcsmons.app.test_client()
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()
        self.assertIn('Version:', data)
        self.assertIn('Counter:', data)

    def test_root_increments_counter(self):
        import mcsmons
        mcsmons.counter = 0
        client = mcsmons.app.test_client()
        client.get('/')
        client.get('/')
        self.assertEqual(mcsmons.counter, 2)


class TestMetrics(unittest.TestCase):
    def setUp(self):
        _create_version_module()
        self._tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump({'servers': ['localhost:25565']}, self._tmp)
        self._tmp.close()
        os.environ['MC_SERVER_JSON'] = self._tmp.name
        sys.modules.pop('mcsmons', None)

    def tearDown(self):
        os.unlink(self._tmp.name)
        sys.modules.pop('mcsmons', None)

    def _make_status(self, description='TestServer', latency=1.23,
                     version_name='1.21', players_max=20, players_online=5,
                     sample=None):
        s = MagicMock()
        s.raw = {}
        s.description = description
        s.latency = latency
        s.version.name = version_name
        s.players.max = players_max
        s.players.online = players_online
        s.players.sample = sample or []
        return s

    def test_metrics_server_online(self):
        import mcsmons
        mock_status = self._make_status()

        with patch('mcsmons.JavaServer') as MockJavaServer:
            MockJavaServer.lookup.return_value.status.return_value = mock_status
            client = mcsmons.app.test_client()
            response = client.get('/metrics')

        self.assertEqual(response.status_code, 200)
        data = response.data.decode()
        self.assertIn('server_online{server_name="localhost:25565"} 1', data)
        self.assertIn('minecraft_latency', data)
        self.assertIn('minecraft_version', data)
        self.assertIn('minecraft_users_max', data)
        self.assertIn('minecraft_users_online', data)

    def test_metrics_server_offline_connection_refused(self):
        import mcsmons
        with patch('mcsmons.JavaServer') as MockJavaServer:
            MockJavaServer.lookup.return_value.status.side_effect = \
                ConnectionRefusedError('refused')
            client = mcsmons.app.test_client()
            response = client.get('/metrics')

        self.assertEqual(response.status_code, 200)
        data = response.data.decode()
        self.assertIn('server_online{server_name="localhost:25565"} 0', data)

    def test_metrics_server_offline_timeout(self):
        import mcsmons
        with patch('mcsmons.JavaServer') as MockJavaServer:
            MockJavaServer.lookup.return_value.status.side_effect = \
                TimeoutError('timeout')
            client = mcsmons.app.test_client()
            response = client.get('/metrics')

        self.assertEqual(response.status_code, 200)
        data = response.data.decode()
        self.assertIn('server_online{server_name="localhost:25565"} 0', data)

    def test_metrics_with_players(self):
        import mcsmons
        player = MagicMock()
        player.name = 'Notch'
        player.uuid = 'some-uuid'
        mock_status = self._make_status(sample=[player])

        with patch('mcsmons.JavaServer') as MockJavaServer:
            MockJavaServer.lookup.return_value.status.return_value = mock_status
            client = mcsmons.app.test_client()
            response = client.get('/metrics')

        data = response.data.decode()
        self.assertIn('minecraft_players', data)
        self.assertIn('Notch', data)

    def test_metrics_forge_server(self):
        import mcsmons
        mock_status = self._make_status()
        mock_status.raw = {'forgeData': True, 'description': {'text': 'ForgeServer'}}

        with patch('mcsmons.JavaServer') as MockJavaServer:
            MockJavaServer.lookup.return_value.status.return_value = mock_status
            client = mcsmons.app.test_client()
            response = client.get('/metrics')

        data = response.data.decode()
        self.assertIn('ForgeServer', data)

    def test_metrics_content_type(self):
        import mcsmons
        with patch('mcsmons.JavaServer') as MockJavaServer:
            MockJavaServer.lookup.return_value.status.side_effect = \
                TimeoutError('timeout')
            client = mcsmons.app.test_client()
            response = client.get('/metrics')

        self.assertIn('text/plain', response.content_type)


if __name__ == '__main__':
    unittest.main()


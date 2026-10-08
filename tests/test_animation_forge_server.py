"""Persistence, cache isolation and local HTTP boundary tests for the editor."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import animation_forge as forge


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = forge.ForgeStore(self.temp.name)
        self.project = forge.core.default_project()

    def tearDown(self):
        self.temp.cleanup()

    def test_save_reopen_new_revisions_and_independent_baseline(self):
        original = copy.deepcopy(self.project)
        self.project['poses'][1]['controls']['right_hand'][0] += 8
        self.project['exposures'][1]['duration_ticks'] += 5
        first = self.store.save(self.project)
        second = self.store.save(self.project)
        self.assertNotEqual(first['file'], second['file'])
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(self.store.load(first['file']), self.project)
        self.assertEqual(self.project['baseline'], original['baseline'])
        self.assertEqual(len(self.store.projects()), 2)
        reopened = forge.ForgeStore(self.temp.name).load(first['file'])
        self.assertEqual(self.store.preview(reopened, 'right'), self.store.preview(self.project, 'right'))

    def test_hold_edit_reuses_pngs_and_pose_edit_is_local(self):
        before = self.store.preview(self.project, 'right')
        files = {p.name: p.read_bytes() for p in (self.store.root/'cache').glob('*.png')}
        self.project['exposures'][0]['duration_ticks'] += 9
        retimed = self.store.preview(self.project, 'right')
        self.assertEqual(before['frames'], retimed['frames'])
        self.assertEqual(retimed['total_ticks'], before['total_ticks']+9)
        self.assertEqual(files, {p.name:p.read_bytes() for p in (self.store.root/'cache').glob('*.png')})
        self.project['poses'][1]['controls']['right_hand'][0] += 5
        edited = self.store.preview(self.project, 'right')
        self.assertNotEqual(edited['frames']['lift']['current'], before['frames']['lift']['current'])
        self.assertEqual(edited['frames']['lift']['baseline'], before['frames']['lift']['baseline'])
        for pose_id in ('neutral', 'reach', 'return'):
            self.assertEqual(edited['frames'][pose_id], before['frames'][pose_id])

    def test_path_escape_and_invalid_projects_rejected_before_write(self):
        with self.assertRaises(ValueError):
            self.store.load('../../anything.json')
        self.project['poses'][0]['controls']['right_hand'][0] = float('nan')
        with self.assertRaises(ValueError):
            self.store.save(self.project)
        self.assertEqual(self.store.projects(), [])

    def test_failed_save_never_publishes_a_partial_revision(self):
        with mock.patch.object(forge.os, 'link', side_effect=OSError('fixture publication failure')):
            with self.assertRaises(OSError):
                self.store.save(self.project)
        self.assertEqual(self.store.projects(), [])
        self.assertEqual(list((self.store.root/'projects').iterdir()), [])


class ReferenceWalkTests(unittest.TestCase):
    def test_reference_files_are_read_only_allowlisted_and_optional(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root/'preserved-proof'
            for name in forge.WALK_FILES:
                path = reference/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(('preserved fixture: '+name).encode())
            original = {name:(reference/name).read_bytes() for name in forge.WALK_FILES}
            server = forge.make_server(root/'editor', 0, reference)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(url+'/api/bootstrap') as response:
                    self.assertTrue(json.load(response)['reference_walk'])
                with urlopen(url+'/reference-walk') as response:
                    self.assertIn(b'reference playback', response.read())
                for name in forge.WALK_FILES:
                    with urlopen(url+'/reference-walk/'+name) as response:
                        self.assertEqual(response.read(), original[name])
                for path in ('v002/render_proof.py', '../outside.txt', 'v002/../../outside.txt'):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(url+'/reference-walk/'+path)
                    self.assertEqual(caught.exception.code,404)
                self.assertEqual(original,{name:(reference/name).read_bytes() for name in forge.WALK_FILES})
                (reference/'v002/playback-data.js').unlink()
                with urlopen(url+'/api/bootstrap') as response:
                    self.assertFalse(json.load(response)['reference_walk'])
                with self.assertRaises(HTTPError) as caught:
                    urlopen(url+'/reference-walk')
                self.assertEqual(caught.exception.code,404)
            finally:
                server.shutdown(); server.server_close(); thread.join()


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = forge.make_server(cls.temp.name, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        with urlopen(cls.url+'/api/bootstrap') as response:
            cls.boot = json.load(response)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def post(self, path, body, **headers):
        return Request(self.url+path, json.dumps(body).encode(),
                       {'Content-Type':'application/json', 'X-Forge-Token':self.boot['token'], **headers})

    def test_real_http_save_load_and_static_editor(self):
        with urlopen(self.post('/api/save', {'project':self.boot['project']})) as response:
            saved = json.load(response)
        with urlopen(self.post('/api/load', {'file':saved['file']})) as response:
            self.assertEqual(json.load(response)['project'], self.boot['project'])
        with urlopen(self.url+'/') as response:
            self.assertIn(b'Animation Forge', response.read())

    def test_cross_origin_missing_token_and_host_rejected(self):
        cases = [self.post('/api/save', {'project':self.boot['project']}, Origin='https://unrelated.example'),
                 self.post('/api/save', {'project':self.boot['project']}, **{'X-Forge-Token':'wrong'}),
                 Request(self.url+'/api/bootstrap', headers={'Host':'unrelated.example'})]
        for req in cases:
            with self.subTest(req=req), self.assertRaises(HTTPError) as caught:
                urlopen(req)
            self.assertEqual(caught.exception.code, 403)

    def test_api_errors_return_json_and_static_cannot_escape(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.post('/api/validate', {'project':{'schema':'wrong'}}))
        self.assertEqual(caught.exception.code,400)
        self.assertIn('error',json.load(caught.exception))
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.url+'/cache/../../tools/animation_forge.py.png')
        self.assertEqual(caught.exception.code,404)

    def test_bootstrap_lists_editable_animation_projects(self):
        self.assertEqual(self.boot['example']['schema'], 'other-animation-forge.v1')
        self.assertTrue(any(item['id']=='reach' for item in self.boot['library']))
        if self.boot['editable_walk']['available']:
            self.assertEqual(self.boot['project']['schema'], 'other-animation-forge.walk.v1')
            self.assertEqual(self.boot['library'][0]['id'], 'walk')
            self.assertEqual(len(self.boot['project']['poses']),72)
            self.assertEqual(self.boot['project']['loop_start'],10)


class WalkStoreTests(unittest.TestCase):
    def test_walk_edit_hold_save_reload_and_cache_preserve_original(self):
        if not forge.walk.availability()['available']:
            self.skipTest('Pinned local research motion is intentionally not bundled')
        with tempfile.TemporaryDirectory() as temp:
            store=forge.ForgeStore(temp)
            project=forge.walk.default_project()
            baseline=copy.deepcopy(project['baseline'])
            before=store.preview(project,'right')
            project['poses'][34]['controls']['right_hand'][0]+=8
            project['exposures'][34]['duration_ticks']=6
            edited=store.preview(project,'right')
            for index,pose in enumerate(project['poses']):
                pair=edited['frames'][pose['id']]
                self.assertEqual(pair['baseline'],before['frames'][pose['id']]['baseline'])
                if index==34:
                    self.assertNotEqual(pair['current'],before['frames'][pose['id']]['current'])
                else:
                    self.assertEqual(pair['current'],before['frames'][pose['id']]['current'])
            saved=store.save(project)
            reopened=store.load(saved['file'])
            self.assertEqual(reopened,project)
            self.assertEqual(reopened['baseline'],baseline)
            self.assertEqual(store.preview(reopened,'right'),edited)
            self.assertEqual(edited['total_ticks'],77)
            self.assertEqual(edited['ground_y'],567)


if __name__ == '__main__':
    unittest.main()

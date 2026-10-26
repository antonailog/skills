import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[4]


def module(name):
    spec = importlib.util.spec_from_file_location(name, REPO/'skills/deep-survey/scripts'/f'{name}.py')
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj


fetch = module('fetch_page'); usage = module('measure_run')


class FetchEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def collector(self, sources, limit=12):
        items = []
        for i, (url, body) in enumerate(sources.items()):
            suffix = '.js' if url.endswith('.js') else '.json' if '/api/' in url else '.html'
            p = self.root/f'raw{i}{suffix}'; p.write_text(body)
            items.append({'url': url, 'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'captured_at': '2026-01-01T00:00:00Z'})
        index = self.root/'index.json'; index.write_text(json.dumps(items))
        return fetch.Collector(self.root/'out', max_requests=limit, replay=index)

    def test_short_data_page_is_not_a_blocked_article(self):
        c = self.collector({'https://example.org/pricing': '<html><body><h1>价格</h1><table><tr><td>标准版</td><td>199 元</td></tr></table></body></html>'})
        r = c.collect('https://example.org/pricing'); self.assertEqual(r['status'], 'ok')
        self.assertIn('199 元', r['text']); self.assertEqual(r['coverage'], 'not_assessed')

    def test_json_hydration_includes_values_hidden_from_body(self):
        state = {'props': {'products': [{'name': 'Pro', 'price': 47, 'currency': 'USD'}], 'description': 'Evidence data ' * 200}}
        body = '<html><body><div id="root"></div><script id="__NEXT_DATA__" type="application/json">'+json.dumps(state)+'</script><script src="/unnecessary.js"></script></body></html>'
        c = self.collector({'https://example.org/': body}); r = c.collect('https://example.org/')
        self.assertEqual(r['status'], 'ok'); self.assertIn('.price: 47', r['text']); self.assertEqual(len(c.requests), 1)

    def test_substantial_static_article_does_not_download_application(self):
        body='<html><body><article>'+('An original paragraph explaining the evidence and its limits. '*100)+'</article><script src="/application.js"></script></body></html>'
        c=self.collector({'https://example.org/post':body}); r=c.collect('https://example.org/post')
        self.assertEqual(r['status'], 'ok'); self.assertEqual(len(c.requests), 1)
        self.assertEqual(r['resource_decisions'][0]['reason'], 'substantial_article')
        r=c.collect('https://example.org/post',resources='all')
        self.assertEqual(r['status'], 'partial'); self.assertEqual(r['missing_resources'][0]['url'],'https://example.org/application.js')

    def test_observed_resource_chain_and_public_get_config(self):
        sources = {'https://example.org/': '<html><body><div id="root"></div><script src="/entry.js"></script></body></html>',
                   'https://example.org/entry.js': 'import "./details.js"; const BASE="/"; const endpoint={url:BASE+"api/prices",type:"get"}; const excluded={url:BASE+"api/orders",type:"post"};',
                   'https://example.org/details.js': 'const record={title:"中文标题隐藏数据",summary:"A technical explanation of persistent states"};',
                   'https://example.org/api/prices': '{"price":199,"currency":"CNY"}'}
        c = self.collector(sources); r = c.collect('https://example.org/')
        self.assertEqual(r['status'], 'ok'); self.assertIn('中文标题隐藏数据', r['text']); self.assertIn('$.price: 199', r['text'])
        self.assertEqual(len(c.requests), 4); self.assertEqual(r['actual_network_requests'], 0)
        self.assertFalse(any('/orders' in x['url'] for x in c.requests))
        self.assertTrue(any(x['method']=='js_literal_heuristic' for x in r['sections']))

    def test_budget_is_partial_and_keeps_collected_evidence(self):
        c = self.collector({'https://example.org/': '<html><body>Some usable original evidence.<script src="/more.js"></script></body></html>'}, limit=1)
        r = c.collect('https://example.org/'); self.assertEqual(r['status'], 'partial')
        self.assertIn('usable original', r['text']); self.assertEqual(r['missing_resources'][0]['reason'], 'request_budget')

    def test_block_page_and_missing_snapshot_never_become_success(self):
        c = self.collector({'https://example.org/': '<html><title>Just a moment</title><body>Verify to continue</body></html>'})
        self.assertEqual(c.collect('https://example.org/')['status'], 'blocked')
        r = c.collect('https://example.org/missing'); self.assertEqual(r['status'], 'partial')
        self.assertEqual(r['actual_network_requests'], 0)

    def test_fragments_do_not_refetch_and_snapshot_hash_is_verified(self):
        c = self.collector({'https://example.org/': '<html><body>Source facts.</body></html>'})
        c.collect('https://example.org/#one'); c.collect('https://example.org/#two'); self.assertEqual(len(c.requests), 1)
        c = self.collector({'https://example.org/': '<html><body>Source facts.</body></html>'})
        (self.root/'raw0.html').write_text('Changed after capture')
        r=c.collect('https://example.org/'); self.assertNotEqual(r['status'], 'ok'); self.assertIn('hash mismatch', r['missing_resources'][0]['reason'])

    def test_private_targets_credentials_and_redirects_are_rejected(self):
        for url in ['file:///etc/passwd', 'https://a:b@example.org', 'http://127.0.0.1/', 'http://[::1]/', 'http://localhost/']:
            with self.assertRaises(ValueError): fetch.public_url(url)
        with patch.object(fetch.socket, 'getaddrinfo', return_value=[(None,None,None,None,('10.0.0.1',80))]):
            with self.assertRaises(ValueError): fetch.public_url('https://example.org/')
        with self.assertRaises(ValueError): fetch.SafeRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1/')

    def test_proxy_fake_ip_is_accepted_only_for_domain_names(self):
        with patch.object(fetch.socket, 'getaddrinfo', return_value=[(None,None,None,None,('198.18.6.12',443))]):
            self.assertEqual(fetch.public_url('https://example.org/'), 'https://example.org/')
        with self.assertRaises(ValueError): fetch.public_url('http://198.18.6.12/')

    def test_js_unicode_is_not_executed_or_corrupted(self):
        self.assertEqual(fetch.decode_js(r'中文\u4e16\u754c\ud83d\ude00'), '中文世界😀')
        self.assertIn('中文内容仅是字符串', fetch.script_evidence('const x="中文内容仅是字符串"; process.exit(9);'))

    def test_http_attempts_count_redirects_but_not_preflight_failures(self):
        records=[]; counter=fetch.RequestCounter(records, 2)
        for url in ('https://example.org/', 'https://example.org/redirected'):
            counter.https_request(fetch.urllib.request.Request(url))
        self.assertEqual(len(records), 2)
        with self.assertRaisesRegex(ValueError, 'request_budget'):
            counter.https_request(fetch.urllib.request.Request('https://example.org/third'))
        c=fetch.Collector(self.root/'network')
        with patch.object(fetch, 'public_url', side_effect=fetch.socket.gaierror('DNS failed')):
            r=c.collect('https://example.org/')
        self.assertEqual(r['network_attempts'], 1); self.assertEqual(r['actual_network_requests'], 0)

    def test_binary_format_is_explicit_and_replay_preserves_capture_time(self):
        c=self.collector({'https://example.org/paper': '%PDF-1.7 binary data'})
        r=c.collect('https://example.org/paper')
        self.assertEqual(r['status'], 'unsupported'); self.assertEqual(r['text'], '')
        c=self.collector({'https://example.org/': '<html><body>Evidence.</body></html>'})
        c.collect('https://example.org/')
        index=self.root/'generated.json'; index.write_text(json.dumps(c.snapshots))
        replay=fetch.Collector(self.root/'again', replay=index)
        r=replay.collect('https://example.org/')
        self.assertEqual(r['snapshots'][0]['captured_at'], '2026-01-01T00:00:00Z')


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
        self.start='2026-01-01T00:00:00Z'; self.end='2026-01-01T00:01:00Z'

    def write(self, name, sid, rows, parent=None):
        payload={'id':sid}
        if parent:payload['source']={'subagent':{'thread_spawn':{'parent_thread_id':parent}}};payload['agent_path']='/root/worker'
        p=self.root/name; data=[{'type':'session_meta','timestamp':self.start,'payload':payload}]+rows
        p.write_text(''.join(json.dumps(x)+'\n' for x in data));return p

    def record(self, rid, thread='root', turn='turn', cached=80, stamp='2026-01-01T00:00:20Z'):
        u={'input_tokens':100,'output_tokens':10,'total_tokens':110,'reasoning_output_tokens':4,'cache_write_input_tokens':0}
        if cached is not None:u['cached_input_tokens']=cached
        return {'type':'token_usage_record','timestamp':stamp,'payload':{'response_id':rid,'thread_id':thread,'turn_id':turn,'usage':u}}

    def test_own_usage_dedup_turn_filter_children_and_cutoff(self):
        r=self.record('r');child=self.record('c',thread='child')
        root=self.write('root.jsonl','root',[r,r,child,self.record('wrong',turn='previous'),self.record('late',stamp='2026-01-01T00:01:01Z'),{'type':'event_msg','timestamp':self.start,'payload':{'total_token_usage':{'total_tokens':999999}}}])
        cp=self.write('child.jsonl','child',[child],parent='root')
        result=usage.measure(root,[cp],'turn',self.start,self.end)
        self.assertEqual(result['model_responses'],2);self.assertEqual(result['aggregate']['total_tokens'],220)
        self.assertEqual(result['aggregate']['uncached_input_tokens'],40);self.assertEqual(result['duplicate_records_ignored'],1)

    def test_missing_cache_is_unknown_not_zero(self):
        root=self.write('root.jsonl','root',[self.record('r',cached=None)])
        r=usage.measure(root,[],'turn',self.start,self.end)
        self.assertIsNone(r['aggregate']['cached_input_tokens']);self.assertIsNone(r['aggregate']['uncached_input_tokens'])
        self.assertEqual(r['aggregate']['total_tokens'],110)

    def test_wrong_child_conflicting_duplicate_and_naive_time_rejected(self):
        root=self.write('root.jsonl','root',[self.record('r')]);cp=self.write('c.jsonl','child',[self.record('c',thread='child')],parent='someone-else')
        with self.assertRaises(ValueError):usage.measure(root,[cp],'turn',self.start,self.end)
        root=self.write('root.jsonl','root',[self.record('r'),self.record('r',cached=70)])
        with self.assertRaises(ValueError):usage.measure(root,[],'turn',self.start,self.end)
        with self.assertRaises(ValueError):usage.instant('2026-01-01T00:00:00')


if __name__=='__main__': unittest.main()

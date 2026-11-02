"""Reject unilateral/partial fixture receipts before named mechanic admission."""
import ast
import copy
import inspect
from pathlib import Path
import tempfile
import tomllib
import unittest

import mmx6_coop_intro_fixture as intro


class NativeScenePredicateTests(unittest.TestCase):
    def test_released_walk_settles_before_idle_assertion(self):
        tree=ast.parse(inspect.getsource(intro.exercise_scene_owner_fatal))
        funcs=[n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name in ('recovered','neutral')]
        idle=dict(observation=dict(ready=1,enrolled=1,lifecycle=(0,5),scene_owner=0,scene_phase=0,pause_owner=0,
            players=[dict(state=1,hp=32,action=2),dict(hp=0)]))
        held=copy.deepcopy(idle);held['observation']['players'][0]['action']=4
        tested=[]
        def wait(label,predicate):
            for p in (held,idle):
                row=dict(peers=[p]);tested.append(predicate(row))
                if tested[-1]:return row
            self.fail('Neutral never settled')
        scope={'wait':wait};exec(compile(ast.Module(body=funcs,type_ignores=[]),'<actual neutral predicate>','exec'),scope)
        self.assertIs(scope['neutral']('released native walk')['peers'][0],idle)
        self.assertEqual(tested,[False,True])

    def test_native_fatal_accepts_source_bound_transient_miss_but_not_wrong_option_or_live_owner(self):
        tree=ast.parse(inspect.getsource(intro.exercise_scene_owner_fatal))
        func=next(n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name=='native_fatal')
        scope={'option':3};exec(compile(ast.Module(body=[func],type_ignores=[]),'<actual native fatal predicate>','exec'),scope)
        p=dict(fatal_option=3,fatal_state=2,observation=dict(scene_owner=2,scene_phase=4,lifecycle=(0,4),players=[dict(hp=32),dict(hp=0)]))
        self.assertTrue(scope['native_fatal'](p))
        p['fatal_option']=4;self.assertFalse(scope['native_fatal'](p));p['fatal_option']=3
        p['observation']['lifecycle']=(0,0);p['observation']['players'][1]['hp']=32
        self.assertFalse(scope['native_fatal'](p))
        p['observation']['lifecycle']=(0,5);p['observation']['players'][1]['hp']=0
        self.assertTrue(scope['native_fatal'](p))
        scope['option']=4;p['fatal_option']=4;p['observation']['scene_phase']=5
        self.assertFalse(scope['native_fatal'](p))
        p['observation']['scene_phase']=4;self.assertTrue(scope['native_fatal'](p))

    def test_live_lifecycle_tuple_and_saved_json_list_use_same_native_guards(self):
        # The debug dataclass retains tuple lifecycle in live .json(); JSON
        # serialization alone hid the mismatch in failed C132 LOCAL1 evidence.
        import json
        import coop_debug as debug
        tree=ast.parse(inspect.getsource(intro.exercise_scene_owner_fatal))
        funcs=[n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name in ('healthy','recovered')]
        self.assertEqual(len(funcs),2)
        scope={};exec(compile(ast.Module(body=funcs,type_ignores=[]),'<actual scene predicates>','exec'),scope)
        players=tuple(debug.Player(1,seat,1,2,32,0,0) for seat in (0,1))
        o=debug.Observation(schema=1,tick=1,sequence=2,native_timer=0,lifecycle=(0,0),pause_owner=0,
            scene_owner=0,scene_phase=0,mailbox=0,ready=1,enrolled=1,failed=0,native_mode=10,
            native_phase=0,host_digest=1,host_digest_algorithm=1,players=players).json()
        self.assertIsInstance(o['lifecycle'],tuple)
        for saved in (False,True):
            active=json.loads(json.dumps(o)) if saved else copy.deepcopy(o)
            self.assertTrue(scope['healthy'](dict(observation=active)))
            active['lifecycle']=(0,5);active['players'][1]['hp']=0
            self.assertTrue(scope['recovered'](dict(observation=active)))
            active['scene_phase']=4
            self.assertFalse(scope['recovered'](dict(observation=active)))


class NamedPrerequisiteCatalogTests(unittest.TestCase):
    def test_weather_fatal_preferences_stay_in_prototype(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source=Path(__file__).resolve().parents[1]
        catalog=(source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text()
        catalog+='\n'+(source/'packaging/lab/coop-checkpoint-option.toml').read_text()
        if not any(o['id']=='lab_fatal' for o in tomllib.loads(catalog)['option']):
            catalog+='\n[[option]]\nfeature="prototype"\nid="lab_fatal"\ntype="choice"\ndefault="off"\n'
            catalog+=''.join('[[option.choice]]\nvalue="'+v+'"\n' for v in ('off','p1','p2'))
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);manifest=directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True);manifest.write_text(catalog)
            state=directory/'mods/state.toml'
            initial='[[feature]]\npackage_id="mmx6.local-coop"\nid = "prototype"\nenabled = false\n[[feature]]\npackage_id="mmx6.enhancement.seamless-loading"\nid="resident"\nenabled=true\n[feature.values]\nstrategy="unchanged"\n'
            state.write_text(initial);trailing=tomllib.loads(initial)['feature'][1]
            pair.select_weather_survivor(directory,enabled=False)
            features=tomllib.loads(state.read_text())['feature'];v=features[0]['values']
            self.assertEqual(features[1],trailing)
            self.assertEqual((v['lab_checkpoint'],v['lab_contact_protection'],v['lab_fatal']),('turtloid_rain_cp1','on','p1'))
            self.assertEqual((v['lab_starting_hp_p1'],v['lab_starting_hp_p2'],v['lab_earned_weapons']),('off','off','off'))
            self.assertEqual((v['local_cameras'],v['cameras']),('split','independent'))

    def test_refight_fatal_stays_in_prototype_before_trailing_feature(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source=Path(__file__).resolve().parents[1]
        catalog=(source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text()
        catalog+='\n'+(source/'packaging/lab/coop-checkpoint-option.toml').read_text()
        if not any(o['id']=='lab_fatal' for o in tomllib.loads(catalog)['option']):
            catalog+='\n[[option]]\nfeature="prototype"\nid="lab_fatal"\ntype="choice"\ndefault="off"\n'
            catalog+=''.join('[[option.choice]]\nvalue="'+value+'"\n' for value in ('off','p1','p2'))
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);manifest=directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True);manifest.write_text(catalog)
            state=directory/'mods/state.toml'
            initial='[[feature]]\npackage_id="mmx6.local-coop"\nid = "prototype"\nenabled = false\n[[feature]]\npackage_id="mmx6.enhancement.seamless-loading"\nid="resident"\nenabled=true\n[feature.values]\nstrategy="unchanged"\n'
            trailing=tomllib.loads(initial)['feature'][1]
            for scenario in ('living','absent','fallen'):
                state.write_text(initial)
                pair.select_refight_policy(directory,enabled=False,scenario=scenario)
                features=tomllib.loads(state.read_text())['feature'];values=features[0]['values']
                self.assertEqual(features[1],trailing)
                self.assertEqual(values['doors'],'both')
                self.assertEqual(values['lab_fatal'],'p1' if scenario=='fallen' else 'off')
                self.assertEqual(values['lab_checkpoint'],'refight_portal_cp1')
                self.assertEqual(values['lab_contact_protection'],'on')
                self.assertEqual((values['lab_starting_hp_p1'],values['lab_starting_hp_p2'],values['lab_earned_weapons']),('off','off','off'))

    def test_door_fallen_seat_selects_actual_survivor_and_lifecycle(self):
        tree=ast.parse(inspect.getsource(intro.exercise_door_policy))
        funcs=[n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name in ('participants','alive')]
        for seat in (0,1):
            scope=dict(excluded=True,scenario='fallen',fallen_seat=seat)
            exec(compile(ast.Module(body=funcs,type_ignores=[]),'<actual fallen-seat predicates>','exec'),scope)
            self.assertEqual(scope['participants'](),(seat^1,))
            players=[dict(active=1,state=1,hp=32),dict(active=1,state=1,hp=32)]
            players[seat].update(state=3,hp=0)
            o=dict(native_mode=10,failed=0,mailbox=0,lifecycle=tuple(5 if x==seat else 0 for x in (0,1)),players=players)
            row=dict(peers=[dict(state=dict(observation=o))])
            self.assertTrue(scope['alive'](row))
            o['lifecycle']=tuple(reversed(o['lifecycle']))
            self.assertFalse(scope['alive'](row))

    def test_door_policy_fatal_stays_in_prototype_before_trailing_net_feature(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source=Path(__file__).resolve().parents[1]
        catalog=(source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text()
        catalog+='\n'+(source/'packaging/lab/coop-checkpoint-option.toml').read_text()
        # Typed catalog extension in the separately built C129 game candidate.
        if not any(o['id']=='lab_fatal' for o in tomllib.loads(catalog)['option']):
            catalog+='\n[[option]]\nfeature="prototype"\nid="lab_fatal"\ntype="choice"\ndefault="off"\n'
            catalog+=''.join('[[option.choice]]\nvalue="'+value+'"\n' for value in ('off','p1','p2'))
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);manifest=directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True);manifest.write_text(catalog)
            state=directory/'mods/state.toml'
            initial='[[feature]]\npackage_id="mmx6.local-coop"\nid = "prototype"\nenabled = false\n[[feature]]\npackage_id="mmx6.enhancement.seamless-loading"\nid="resident"\nenabled=true\n[feature.values]\nstrategy="unchanged"\n'
            trailing=tomllib.loads(initial)['feature'][1]
            for scenario in ('either','living','absent','fallen'):
                state.write_text(initial)
                pair.select_door_policy(directory,enabled=False,scenario=scenario)
                features=tomllib.loads(state.read_text())['feature'];values=features[0]['values']
                self.assertEqual(features[1],trailing)
                self.assertEqual(values['doors'],'either' if scenario=='either' else 'both')
                self.assertEqual(values['lab_fatal'],'p2' if scenario=='fallen' else 'off')
                self.assertEqual(values['lab_checkpoint'],'intro_cp2' if scenario=='either' else 'intro_before_doors')
                self.assertEqual(values['lab_contact_protection'],'on')
                self.assertEqual((values['lab_starting_hp_p1'],values['lab_starting_hp_p2'],values['lab_earned_weapons']),('off','off','off'))

            state.write_text(initial)
            pair.select_door_policy(directory,enabled=False,scenario='fallen',fallen_seat=0)
            features=tomllib.loads(state.read_text())['feature']
            self.assertEqual(features[0]['values']['lab_fatal'],'p1')
            self.assertEqual(features[0]['values']['doors'],'both')
            self.assertEqual(features[1],trailing)

    def test_existing_fatal_selectors_accept_capsule_catalog_without_selecting_capsule(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source=Path(__file__).resolve().parents[1]
        catalog=(source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text()
        catalog+='\n'+(source/'packaging/lab/coop-checkpoint-option.toml').read_text()
        fatal_begin=catalog.index('\n[[option]]\nfeature = "prototype"\nid = "lab_fatal"')
        fatal_end=catalog.find('\n[[option]]',fatal_begin+1)
        if fatal_end<0:fatal_end=len(catalog)
        fatal=catalog[fatal_begin:fatal_end]
        fatal=fatal[:fatal.index('\n[[option.choice]]\nvalue = "capsule_owner_p1"')]
        prefix,suffix=catalog[:fatal_begin]+fatal,catalog[fatal_end:]
        capsule='\n[[option.choice]]\nvalue="capsule_owner_p1"\nlabel="Native capsule owner fatal"\n'
        cases=((pair.select_door_policy,dict(scenario='fallen',fallen_seat=0),'intro_before_doors'),
               (pair.select_refight_policy,dict(scenario='fallen'),'refight_portal_cp1'),
               (pair.select_weather_survivor,{},'turtloid_rain_cp1'))
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);manifest=directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True);state=directory/'mods/state.toml'
            initial='[[feature]]\npackage_id="mmx6.local-coop"\nid = "prototype"\nenabled = false\n'
            for select,arguments,checkpoint in cases:
                for extension in ('',capsule):
                    with self.subTest(selector=select.__name__,capsule=bool(extension)):
                        manifest.write_text(prefix+extension+suffix);state.write_text(initial)
                        select(directory,enabled=False,**arguments)
                        values=tomllib.loads(state.read_text())['feature'][0]['values']
                        self.assertEqual(values['lab_fatal'],'p1')
                        self.assertEqual(values['lab_checkpoint'],checkpoint)
                        self.assertEqual((values['lab_starting_hp_p1'],values['lab_starting_hp_p2'],values['lab_earned_weapons']),('off','off','off'))
                manifest.write_text(prefix+capsule+'\n[[option.choice]]\nvalue="unknown_fatal"\n'+suffix)
                state.write_text(initial)
                with self.assertRaises(ValueError):select(directory,enabled=False,**arguments)

    def test_midboss_both_stays_in_prototype_with_trailing_net_feature(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        catalog = (source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text()
        catalog += '\n'+(source/'packaging/lab/coop-checkpoint-option.toml').read_text()
        marker = '[[option.choice]]\nvalue = "heatnix_cp7"'
        catalog = catalog.replace(marker, '[[option.choice]]\nvalue = "heatnix_cp0"\nlabel = "Magma CP0"\n'+marker, 1)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(catalog)
            state = directory/'mods/state.toml'
            initial = '\n'.join(('[[feature]]', 'package_id = "mmx6.local-coop"',
                'id = "prototype"', 'enabled = false', '[[feature]]',
                'package_id = "mmx6.enhancement.seamless-loading"', 'id = "resident"',
                'enabled = true', '[feature.values]', 'strategy = "unchanged"', ''))
            state.write_text(initial)
            trailing = tomllib.loads(initial)['feature'][1]
            receipt = pair.select_midboss(directory, enabled=False)
            parsed = tomllib.loads(state.read_text())
            self.assertEqual(parsed['feature'][0]['values']['doors'], 'both')
            self.assertEqual(parsed['feature'][0]['values']['lab_checkpoint'], 'heatnix_cp0')
            self.assertEqual(parsed['feature'][0]['values']['lab_earned_weapons'], 'all')
            self.assertEqual(parsed['feature'][1], trailing)
            self.assertEqual(receipt['doors'], 'both')

    def test_subtank_policy_stays_in_prototype_before_later_packages(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary); manifest=directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text((source/'packaging/lab/coop-checkpoint-option.toml').read_text(),encoding='utf-8')
            state=directory/'mods/state.toml'
            state.write_text('[[feature]]\npackage_id = "mmx6.local-coop"\nid = "prototype"\nenabled = false\n'
                '[[package]]\nid = "later-package"\nversion = "1"\n[[feature]]\npackage_id = "later-package"\nid = "later"\nenabled = true\n',encoding='utf-8')
            pair.select_subtank_policy(directory,enabled=False)
            parsed=tomllib.loads(state.read_text())
            self.assertEqual(parsed['feature'][0]['values']['subtank_energy'],'independent')
            self.assertEqual(parsed['feature'][0]['values']['lab_checkpoint'],'intro_subtank_cp2')
            self.assertEqual(parsed['feature'][0]['values']['lab_starting_hp_p1'],'13')
            self.assertEqual(parsed['feature'][0]['values']['lab_starting_hp_p2'],'11')
            self.assertNotIn('subtank_energy',parsed['package'][0])
            self.assertNotIn('values',parsed['feature'][1])

    def test_named_positions_are_explicit_lab_only_with_strict_choice_set(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        normal = tomllib.loads((source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text(encoding='utf-8'))
        self.assertFalse(any(o.get('id') in ('lab_checkpoint', 'lab_contact_protection', 'lab_starting_hp_p1', 'lab_starting_hp_p2', 'lab_earned_weapons', 'lab_fatal', 'lab_hatch_stagger') for o in normal.get('option', [])))
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'
            initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            state.write_text(initial, encoding='utf-8')
            for option in ('intro_subtank_cp2', 'intro_before_doors', 'intro_before_explosion', 'recycle_cp2', 'recycle_portal_cp2', 'recycle_distant_cp2', 'recycle_fallen_cp2', 'recycle_fallen_guest_cp2', 'secretlab2b_enemy_cp0', 'refight_portal_cp1', 'refight_distant_cp1', 'heatnix_cp7', 'heatnix_cp0', 'sigma_cp1', 'northpole_ice_cp3', 'turtloid_rain_cp1', 'alternate_boss_cp1'):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option=option)
                self.assertEqual(receipt['option'], option)
                self.assertIn('lab_checkpoint = "'+option+'"', state.read_text(encoding='utf-8'))
            state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='arbitrary_position')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            # Recycle must be present in the exact agreed catalog. An otherwise
            # current old catalog cannot admit a unilateral new destination.
            recycle_choice = '\n[[option.choice]]\nvalue = "recycle_cp2"\nlabel = "Recycle section 1 checkpoint 2 prerequisite"\n'
            self.assertIn(recycle_choice, catalog)
            manifest.write_text(catalog.replace(recycle_choice, ''), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='recycle_cp2')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            # An old five-choice catalog cannot silently authorize the newly
            # named destination; every peer must hash the exact current set.
            old_catalog = catalog[:catalog.index('\n[[option.choice]]\nvalue = "intro_before_explosion"')]
            manifest.write_text(old_catalog, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='intro_before_explosion')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            manifest.write_text(catalog.replace('value = "intro_before_doors"', 'value = "arbitrary_position"'), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='intro_before_doors')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)

    def test_partner_x_armor_is_a_default_base_prototype_choice(self):
        source=Path(__file__).resolve().parents[1]
        catalog=tomllib.loads((source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text())
        options=[o for o in catalog['option'] if o['id']=='partner_x_armor']
        self.assertEqual(len(options),1)
        self.assertEqual((options[0]['feature'],options[0]['type'],options[0]['default']),('prototype','choice','base'))
        self.assertEqual([c['value'] for c in options[0]['choice']],['base','falcon','shadow','blade'])

    def test_native_fatal_is_an_explicit_default_off_lab_choice(self):
        source=Path(__file__).resolve().parents[1]
        catalog=tomllib.loads((source/'packaging/lab/coop-checkpoint-option.toml').read_text())
        options=[o for o in catalog['option'] if o['id']=='lab_fatal']
        self.assertEqual(len(options),1)
        self.assertEqual((options[0]['feature'],options[0]['type'],options[0]['default']),('prototype','choice','off'))
        self.assertEqual([c['value'] for c in options[0]['choice']],['off','p1','p2','scene_before_release','scene_during_arrival','capsule_owner_p1','boss_admission_p1'])

    def test_hatch_stagger_is_an_explicit_default_off_lab_choice(self):
        source=Path(__file__).resolve().parents[1]
        catalog=tomllib.loads((source/'packaging/lab/coop-checkpoint-option.toml').read_text())
        options=[o for o in catalog['option'] if o['id']=='lab_hatch_stagger']
        self.assertEqual(len(options),1)
        self.assertEqual((options[0]['feature'],options[0]['type'],options[0]['default']),('prototype','choice','off'))
        self.assertEqual([c['value'] for c in options[0]['choice']],['off','on'])

    def test_protection_requires_explicit_typed_prelaunch_choice(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True); manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'; initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            for selected in ('off', 'on'):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option='recycle_cp2', contact_protection=selected)
                self.assertEqual(receipt['option'], 'recycle_cp2')
                self.assertEqual(receipt['contact_protection'], selected)
                parsed = tomllib.loads(state.read_text(encoding='utf-8'))
                self.assertEqual(parsed['feature'][0]['values']['lab_contact_protection'], selected)
                self.assertEqual(parsed['feature'][0]['values']['lab_checkpoint'], 'recycle_cp2')
                self.assertEqual(state.read_text(encoding='utf-8').count('lab_checkpoint ='), 1)
                self.assertEqual(state.read_text(encoding='utf-8').count('lab_contact_protection ='), 1)
            state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, contact_protection='arbitrary')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            manifest.write_text(catalog.replace('id = "lab_contact_protection"', 'id = "unrelated"'), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, contact_protection='on')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)

    def test_starting_hp_pair_is_exact_typed_prelaunch_only(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True); manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'; initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            for hp in (('off', 'off'), ('1', '32'), ('17', '23')):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option='turtloid_rain_cp1', starting_hp=hp)
                values = tomllib.loads(state.read_text())['feature'][0]['values']
                self.assertEqual(receipt['starting_hp'], list(hp))
                self.assertEqual([values['lab_starting_hp_p1'], values['lab_starting_hp_p2']], list(hp))
                for key in ('lab_checkpoint', 'lab_starting_hp_p1', 'lab_starting_hp_p2'):
                    self.assertEqual(state.read_text().count(key+' ='), 1)
            for hp in ((1, 'off'), ('0', 'off'), ('33', 'off'), ('01', 'off'), ('1',), '1'):
                state.write_text(initial, encoding='utf-8')
                with self.subTest(hp=hp), self.assertRaises(ValueError):
                    pair.select_checkpoint(directory, enabled=True, starting_hp=hp)
                self.assertEqual(state.read_text(), initial)
            bad = catalog.replace('value = "32"', 'value = "33"')
            manifest.write_text(bad, encoding='utf-8');state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, starting_hp=('1', 'off'))
            self.assertEqual(state.read_text(), initial)

    def test_earned_weapons_commits_with_hp_and_refuses_unavailable_catalog(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True); manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'; initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            for selected in ('off', 'all'):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option='recycle_cp2',
                    starting_hp=('17', '23'), earned_weapons=selected)
                values = tomllib.loads(state.read_text())['feature'][0]['values']
                self.assertEqual(receipt['earned_weapons'], selected)
                self.assertEqual(values['lab_earned_weapons'], selected)
                self.assertEqual([values['lab_starting_hp_p1'], values['lab_starting_hp_p2']], ['17', '23'])
            state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, earned_weapons='invalid')
            self.assertEqual(state.read_text(), initial)
            manifest.write_text(catalog.replace('id = "lab_earned_weapons"', 'id = "unavailable"'), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, earned_weapons='all')
            self.assertEqual(state.read_text(), initial)

    def test_hp_receipt_is_separate_from_checkpoint_authority(self):
        class Client:
            def read(self, address, size):
                self.requested = (address, size); return bytes((2, 1, 0, 1))
        client = Client(); actual = intro.starting_hp_receipt(client)
        self.assertEqual(actual, dict(status=2, requested=[1, 0], applied_mask=1, raw_hex='02010001'))
        self.assertEqual(client.requested, (intro.debug.DIAGNOSTIC_ADDRESS+0xC0, 4))


class NegotiatedReceiptTests(unittest.TestCase):
    def complete(self):
        return dict(generation=1, state=3, reason=0, stage=0, section=0, checkpoint=2,
            nonce=intro.NONCE, initializer_entries=1, record=intro.RECORD, tainted=1,
            authority=1, latch=2, prior_chord=0)

    def test_matching_one_shot_receipts_and_ordinary_mailbox_are_distinct(self):
        good = self.complete()
        self.assertEqual(intro.validate_completion([good, copy.deepcopy(good)])['checkpoint'], 2)
        for field, value in (('authority', 0), ('tainted', 0), ('latch', 1), ('state', 2),
                             ('initializer_entries', 0), ('initializer_entries', 2), ('generation', 2),
                             ('nonce', 1), ('record', '8007212C'), ('checkpoint', 1), ('reason', 1)):
            wrong = dict(good, **{field:value})
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                intro.validate_completion([good, wrong])

    def test_missing_peer_empty_and_noninteger_receipts_are_refused(self):
        good = self.complete()
        for values in ([], [good, good, good], [good, {}], [dict(good, authority=True)]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                intro.validate_completion(values)


class NativeControlWitnessTests(unittest.TestCase):
    def row(self):
        players = [dict(character=seat, state=1, hp=32, action=2, x_raw=100*65536) for seat in (0, 1)]
        return dict(peers=[dict(peer=0, observation=dict(players=players))])

    def test_controlled_native_walk_and_genuine_other_actor_damage_are_separate(self):
        before = self.row(); after = copy.deepcopy(before)
        after['peers'][0]['observation']['players'][0].update(action=3, x_raw=97*65536)
        self.assertTrue(intro.independent_walk(before, after, 0)[0]['other_stationary'])
        after['peers'][0]['observation']['players'][0]['action'] = 4
        self.assertTrue(intro.independent_walk(before, after, 0))
        other = after['peers'][0]['observation']['players'][1]
        other.update(x_raw=101*65536)
        self.assertIsNone(intro.independent_walk(before, after, 0))
        other.update(hp=30, action=17)
        witness = intro.independent_walk(before, after, 0)[0]
        self.assertFalse(witness['other_stationary']); self.assertTrue(witness['other_HP_drop'])
        after['peers'][0]['observation']['players'][0]['action'] = 17
        self.assertIsNone(intro.independent_walk(before, after, 0))

    def test_dead_nonparticipant_cannot_supply_restored_controls(self):
        before = self.row(); after = copy.deepcopy(before)
        after['peers'][0]['observation']['players'][1].update(action=4, x_raw=97*65536)
        after['peers'][0]['observation']['players'][0]['hp'] = 0
        self.assertIsNone(intro.independent_walk(before, after, 1))


class NativeTransportBoundaryTests(unittest.TestCase):
    def test_Turtloid_receipt_with_old_bodies_or_incoming_actors_is_not_arrival(self):
        def peer(x=1120, incoming=False):
            bodies=[]
            for seat in (0,1):
                body=bytearray(0x158);body[0]=1;body[2]=seat
                body[4:6]=bytes((1,0 if incoming else 2));body[0x70]=8
                bodies.append(body.hex())
            return dict(observation=dict(players=[dict(x_raw=x*65536)]),
                        p1_body_hex=bodies[0],p2_body_hex=bodies[1])
        self.assertFalse(intro.turtloid_checkpoint_arrivals([peer(359)]))
        self.assertFalse(intro.turtloid_checkpoint_arrivals([peer(incoming=True)]))
        self.assertTrue(intro.turtloid_checkpoint_arrivals([peer(),peer()]))

    def test_zero_HP_passenger_requires_actual_transport_phase_and_alive_lifecycle(self):
        value = dict(scene_owner=1, scene_phase=2, lifecycle=[0, 0], players=[dict(hp=32), dict(hp=0)])
        self.assertTrue(intro.native_admission_health(value, 0))
        for change in (dict(scene_owner=0), dict(scene_owner=2), dict(scene_phase=0),
                       dict(scene_phase=1), dict(scene_phase=4), dict(scene_phase=5),
                       dict(lifecycle=[0, 3]), dict(lifecycle=[0, 4]), dict(lifecycle=[0, 5])):
            with self.subTest(change=change):
                self.assertFalse(intro.native_admission_health(dict(value, **change), 0))
        value['players'][0]['hp'] = 0
        self.assertFalse(intro.native_admission_health(value, 0))

    def test_CP2_metadata_with_old_CP0_bodies_does_not_establish_arrival(self):
        def peers(xs):
            return [dict(checkpoint=2, observation=dict(players=[dict(x_raw=x*65536) for x in xs]))]
        self.assertFalse(intro.authored_checkpoint_arrivals(peers((144, 168))))
        self.assertTrue(intro.authored_checkpoint_arrivals(peers((5904, 5928))))
        self.assertFalse(intro.authored_checkpoint_arrivals([]))


if __name__ == '__main__':
    unittest.main()

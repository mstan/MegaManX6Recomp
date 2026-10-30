"""Bounded source/typed-policy checks; actual-plugin C fixture is separate."""
import hashlib, json, os, struct, subprocess, tomllib, unittest
from pathlib import Path
import mmx6_host_lab_contract

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=(ROOT/'src/mods/mmx6_coop_plugin.c').read_text(encoding='utf-8')
CHECKPOINT=(ROOT/'src/mods/mmx6_coop_checkpoint.inc').read_text(encoding='utf-8')
SNAPSHOT=(ROOT/'src/mods/mmx6_coop_snapshot.inc').read_text(encoding='utf-8')

def function(text,name):
    start=text.index('static ',text.index(name)-32)
    first=text.index('{',text.index(name));depth=1;end=first+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

class EarnedWeapons(unittest.TestCase):
    def test_lab_only_typed_default(self):
        lab=tomllib.loads((ROOT/'packaging/lab/coop-checkpoint-option.toml').read_text())
        option=next(x for x in lab['option']if x['id']=='lab_earned_weapons')
        self.assertEqual((option['feature'],option['type'],option['default']),('prototype','choice','off'))
        self.assertEqual({x['value']for x in option['choice']},{'off','all'})
        normal=tomllib.loads((ROOT/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text())
        self.assertNotIn('lab_earned_weapons',{x['id']for x in normal['option']})

    def test_native_initializer_authentication(self):
        path=os.environ.get('MMX6_CONTENT_EXE')
        if not path:self.skipTest('Original EXE required')
        data=Path(path).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),'dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046')
        code=data[0x3D718-0x10000+2048:0x3D7AC-0x10000+2048]
        self.assertEqual(hashlib.sha256(code).hexdigest(),'d2cc0660040709245080d3e570746ce3247ec4b9064a251b0a08ce42112e0e8e')
        value=2166136261
        for b in code:value=((value^b)*16777619)&0xffffffff
        self.assertEqual(value,0xE818BDD7)
        stores=[]
        for (word,)in struct.iter_unpack('<I',code):
            if word>>26 in(0x28,0x2B)and (word>>21)&31==5:stores.append(word&0xffff)
        self.assertEqual(stores,[0xE7,0xEC,0xC9,0xC9])
        self.assertNotIn(0x5C,stores);self.assertNotIn(0x93,stores)

    def test_offline_command9_policy_is_exactly_preserved(self):
        before=subprocess.check_output(['git','-C',str(ROOT),'show','f461288646db296a7eccdf59f68f5f7bc5a42ba1:src/mods/mmx6_coop_plugin.c'],text=True)
        actual=function(PLUGIN,'diagnostic_inventory_setup')
        actual=actual.replace('!checkpoint_equipment_source()','checkpoint_hash(0x8003D718u,0x8003D7ACu)!=0xe818bdd7u')
        actual=actual.replace('    checkpoint_equipment_native(cpu,mask);','    psx_mod_write_byte(PLAY+0x60,(uint8_t)mask);\n    guest(cpu,0x8003D718,PLAYER,0);\n    enter_zero();\n    guest(cpu,0x8003D718,PLAYER,0);\n    leave_zero();')
        self.assertEqual(actual,function(before,'diagnostic_inventory_setup'))

    def test_grant_follows_original_healthy_completion_only(self):
        arm=function(CHECKPOINT,'checkpoint_lab_boundary');body=function(CHECKPOINT,'checkpoint_complete')
        self.assertNotIn('checkpoint_equipment_native',arm);self.assertNotIn('checkpoint_equipment_lab',arm)
        self.assertIn('checkpoint_request(',arm)
        for guard in('checkpoint_lab_authorized()','checkpoint_equipment_source()','checkpoint_before_doors_idle(0)','b[0x5C]!=full','b[0x5D]!=full','b[0x5E]!=full'):
            self.assertLess(body.index(guard),body.index('checkpoint_equipment_lab(cpu)'))
        self.assertLess(body.index('checkpoint_equipment_lab(cpu)'),body.index('checkpoint_earned_weapons_applied=1'))
        self.assertLess(body.index('checkpoint_earned_weapons_applied=1'),body.index('if(hp_pending)'))
        self.assertLess(body.index('checkpoint_earned_weapons_applied=1'),body.index('CHECKPOINT_COMPLETE'))

    def test_lab_restores_campaign_after_both_projection_calls(self):
        body=function(CHECKPOINT,'checkpoint_equipment_lab')
        self.assertIn('campaign=psx_mod_read_byte(PLAY+0x60)',body)
        self.assertIn('STATE_WORDS(restore_campaign,67,&campaign,1)',body)
        self.assertLess(body.index('checkpoint_equipment_native(cpu,0xFFu)'),body.index('psx_mod_write_byte(PLAY+0x60,(uint8_t)campaign)'))
        self.assertLess(body.index('psx_mod_write_byte(PLAY+0x60,(uint8_t)campaign)'),body.index('STATE_POP(restore_campaign)'))

    def test_native_primitive_has_no_body_or_outcome_writes(self):
        body=function(CHECKPOINT,'checkpoint_equipment_native')
        self.assertEqual(body.count('psx_mod_write_'),1)
        self.assertIn('psx_mod_write_byte(PLAY+0x60,(uint8_t)mask)',body)
        self.assertEqual(body.count('guest(cpu,0x8003D718u,PLAYER,0)'),2)
        self.assertIn('enter_zero()',body);self.assertIn('leave_zero()',body)

    def test_reset_snapshot_and_option_identity(self):
        self.assertIn('checkpoint_earned_weapons_option=checkpoint_earned_weapons_applied=checkpoint_earned_weapons_reason=0',CHECKPOINT)
        self.assertIn('checkpoint_earned_weapons_option && !checkpoint_lab_option',CHECKPOINT)
        for s in('s->earned_applied=checkpoint_earned_weapons_applied','FIELD(earned_applied,1,1)',
                  'checkpoint_earned_weapons_applied=s->earned_applied','state_fixed(s,checkpoint_earned_weapons_option)',
                  'state_fixed(s,15)'):
            self.assertIn(s,SNAPSHOT)
        digest=function(SNAPSHOT,'state_digest')
        resources=digest.split('const uint32_t resources[]={',1)[1].split('};',1)[0]
        self.assertIn('checkpoint_earned_weapons_option',resources.split(','))

    def test_current_profile_and_old_title_refusal(self):
        contract=json.loads((ROOT/'docs/COOP_HOST_LAB_CONTRACT.json').read_text())
        self.assertEqual(contract['revision'],39)
        self.assertEqual(contract['session']['title_compatibility'],'mmx6-x-zero-delay-v56')
        self.assertEqual((ROOT/'src/mods/mmx6_coop_host_lab_contract.h').read_text(),mmx6_host_lab_contract.generated_header())
        test=(ROOT/'tests/test_mmx6_coop_host_lab.c').read_text()
        self.assertIn('title.compatibility_id="mmx6-x-zero-delay-v37";CHECK(!lab_title_eligible(&title))',test)
        self.assertIn('MMX6_STARTUP_BUILD_ID=\\"mmx6-x-zero-delay-v56\\"',(ROOT/'CMakeLists.txt').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()

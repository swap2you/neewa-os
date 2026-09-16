import hashlib,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'16_WINDOWS_CLIENT'
class WindowsPackageTests(unittest.TestCase):
 def test_installer_has_trust_checks(self):
  s=(BASE/'Install-NEEWA.ps1').read_text();self.assertIn('Get-AuthenticodeSignature',s);self.assertIn('O=Nous Research Inc',s);self.assertIn('ConfirmPersonalDevice',s);self.assertIn('env:Path',s);self.assertIn('win-unpacked\\Hermes.exe',s);self.assertNotIn("Arguments='desktop'",s)
 def test_installer_has_no_embedded_secret_assignments(self):
  s=(BASE/'Install-NEEWA.ps1').read_text().lower();self.assertNotIn('api_key=',s);self.assertNotIn('password=',s);self.assertNotIn('token=',s);self.assertNotIn('private key',s)
 def test_no_public_bind_or_funnel(self):
  s='\n'.join(x.read_text(errors='ignore') for x in BASE.rglob('*') if x.is_file() and x.suffix!='.zip');self.assertNotIn('0.0.0.0',s);self.assertNotIn('tailscale funnel --',s.lower())
 def test_archive_contains_only_reviewed_files(self):
  expected={'NEEWA-Windows-Bootstrap/README.md','NEEWA-Windows-Bootstrap/Install-NEEWA.ps1','NEEWA-Windows-Bootstrap/Uninstall-NEEWA-Client.ps1','NEEWA-Windows-Bootstrap/assets/neewa.yaml','NEEWA-Windows-Bootstrap/assets/neewa-command-center/plugin.js'}
  with zipfile.ZipFile(BASE/'dist/NEEWA-Windows-Bootstrap.zip') as z:self.assertIsNone(z.testzip());self.assertEqual(expected,set(z.namelist()))
 def test_plugin_and_skin_exist(self):self.assertTrue((BASE/'assets/neewa.yaml').is_file());self.assertTrue((BASE/'assets/neewa-command-center/plugin.js').is_file())
if __name__=='__main__':unittest.main()

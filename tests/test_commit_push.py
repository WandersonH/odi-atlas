import os, shutil, subprocess, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CAB = "candidate_id;candidate_name;platform;url;followers;captured_at;source_url\n"


def sh(cwd, *a):
    return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True).stdout


@unittest.skipIf(shutil.which("git") is None, "sem git")
class TestCommitPush(unittest.TestCase):
    def test_duas_coletas_no_mesmo_arquivo(self):
        t = Path(tempfile.mkdtemp())
        sh(t, "git", "init", "-q", "--bare", "-b", "main", "origem.git")
        a = t / "a"
        sh(t, "git", "clone", "-q", str(t / "origem.git"), "a")
        for c in (a,):
            sh(c, "git", "config", "user.email", "x@x"); sh(c, "git", "config", "user.name", "x")
        (a / "scripts").mkdir()
        for f in ("commit_push.sh", "resolver_conflitos.py"):
            shutil.copy(RAIZ / "scripts" / f, a / "scripts" / f)
        (a / "data/seguidores").mkdir(parents=True)
        (a / "data/seguidores/latest.csv").write_text(CAB + "1;L;Instagram;u1;10;2026-10-18;s\n1;L;YouTube;u2;20;2026-10-18;s\n")
        (a / "data/seguidores/variacao.json").write_text('{"v":0}')
        sh(a, "git", "add", "-A"); sh(a, "git", "commit", "-qm", "base"); sh(a, "git", "push", "-q", "origin", "HEAD:main")
        b = t / "b"
        sh(t, "git", "clone", "-q", str(t / "origem.git"), "b")
        sh(b, "git", "config", "user.email", "x@x"); sh(b, "git", "config", "user.name", "x")
        # coleta A (Meta) atualiza o Instagram e envia primeiro
        (a / "data/seguidores/latest.csv").write_text(CAB + "1;L;Instagram;u1;11;2026-10-19;s\n1;L;YouTube;u2;20;2026-10-18;s\n")
        (a / "data/seguidores/variacao.json").write_text('{"v":"meta"}')
        sh(a, "bash", "scripts/commit_push.sh", "meta")
        # coleta B (YouTube), começou antes, atualiza o YouTube no mesmo arquivo
        (b / "data/seguidores/latest.csv").write_text(CAB + "1;L;Instagram;u1;10;2026-10-18;s\n1;L;YouTube;u2;22;2026-10-19;s\n")
        (b / "data/seguidores/variacao.json").write_text('{"v":"youtube"}')
        env = {**os.environ, "GITHUB_REF_NAME": "main"}
        r = subprocess.run(["bash", "scripts/commit_push.sh", "youtube"], cwd=b, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        final = sh(b, "git", "show", "origin/main:data/seguidores/latest.csv")
        self.assertIn("1;L;Instagram;u1;11;2026-10-19;s", final)  # a coleta Meta não foi apagada
        self.assertIn("1;L;YouTube;u2;22;2026-10-19;s", final)    # a do YouTube entrou
        self.assertEqual(sh(b, "git", "show", "origin/main:data/seguidores/variacao.json"), '{"v":"youtube"}')
        shutil.rmtree(t)


if __name__ == "__main__":
    unittest.main()

"""Build an attributed derivative with bounds and command-budget fixes."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = ROOT / "reference/shuang96/main.cpp"
OUT = ROOT / "versions/v6_attributed96"
ATTRIBUTION = """// Based on Shuang-su/SZTU-2026-data-structure-final-homework.
// Upstream commit: a35a23f3a8a3c623ff9c62af15e680143264de5e.
// Local changes: successor bounds and atomic per-tick command budgets.
"""


def main():
    source = ORIGIN.read_text(encoding="utf8")

    def replace(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)

    replace("string outbuf;", """string outbuf;
constexpr int COMMAND_LIMIT = 20000;
int commandsUsed;
vector<int> deferredKills;
size_t deferredHead;""")
    replace("ll dst(int a, int b)", """// Stop requests beyond the current command budget survive to the next tick.
// Events may finish or interrupt a queued job before then; those requests expire.
void killNow(int ji) {
    assert(commandsUsed < COMMAND_LIMIT);
    outbuf += "KILL " + to_string(jobs[ji].id) + "\\n";
    ++commandsUsed;
    release(ji);
}
void stopOrDefer(int ji) {
    if (jobs[ji].state != 1) return;
    if (commandsUsed < COMMAND_LIMIT) killNow(ji);
    else deferredKills.push_back(ji);
}
void drainDeferredKills() {
    while (deferredHead < deferredKills.size() && commandsUsed < COMMAND_LIMIT) {
        int ji = deferredKills[deferredHead++];
        if (jobs[ji].state == 1) killNow(ji);
    }
    if (deferredHead == deferredKills.size()) deferredKills.clear(), deferredHead = 0;
}

ll dst(int a, int b)""")
    replace("void runJob(int ji, int x) {", """void runJob(int ji, int x) {
    assert(commandsUsed < COMMAND_LIMIT);
    ++commandsUsed;""")
    replace("        for (int si : j.suc) {\n            Job& s = jobs[si];",
            """        for (int si : j.suc) {
            if (ns >= 8) break;  // Check before any access to qr/ns scratch rows.
            Job& s = jobs[si];""")
    replace("            if (!k || ns > 7) continue;", "            if (!k) continue;")
    replace("    int rdy = j.ready;", """    // RUN/KILL/RUN is one atomic decision: never emit a partial prewarm batch.
    if (commandsUsed + (bwarm ? 3 : 1) > COMMAND_LIMIT) return;
    int rdy = j.ready;""")
    replace('        outbuf += "KILL " + to_string(j.id) + "\\n";\n        release(ji);',
            "        killNow(ji);")
    replace("void schedule() {", """void schedule() {
    drainDeferredKills();""")
    replace('                    outbuf += "KILL " + to_string(jobs[w.first + i].id) + "\\n";\n                    release(w.first + i);',
            "                    stopOrDefer(w.first + i);")
    replace('        outbuf += "\\n";\n        schedule();',
            '        outbuf += "\\n";\n        commandsUsed = 0;\n        schedule();')
    OUT.mkdir(parents=True, exist_ok=True)
    raw = (ATTRIBUTION + source).encode("utf8")
    (OUT / "main.cpp").write_bytes(raw)
    manifest = {"upstream_repository": "https://github.com/Shuang-su/SZTU-2026-data-structure-final-homework",
                "upstream_commit": "a35a23f3a8a3c623ff9c62af15e680143264de5e",
                "upstream_working_source_sha256": hashlib.sha256(ORIGIN.read_bytes()).hexdigest(),
                "source": str(OUT / "main.cpp"), "source_sha256": hashlib.sha256(raw).hexdigest(),
                "source_bytes": len(raw), "attribution_preserved": True,
                "identifier_obfuscation": False, "official_submission_sent": False,
                "changes": ["Check successor scratch bounds before accessing row 8",
                            "Count all RUN and KILL commands against 20000 per tick",
                            "Reserve all three commands before a prewarm batch",
                            "Defer excess stop requests across ticks and expire DONE/FAIL requests"]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()

# AI 写完代码，空 diff 也可能漏审 / An empty diff can miss code

这是可复用的原创讨论样例。2026-10-08T00:20:53.609914Z 已在三个独立临时仓库运行，环境为 **Git 2.55.0**。只复现 Git 文件状态，没有调用模型；这些结果不证明 AI 编程表现或任何涨粉效果。临时仓库已移除，用户项目未参与实验。

This reusable discussion example was reproduced in three separate temporary repositories on **Git 2.55.0**, at 2026-10-08T00:20:53.609914Z. It tests Git file states only: no model calls, AI performance claims, or follower-growth evidence. The temporary repositories were removed; no user project was used.

## 实测结果 / Observed results

| 状态 / State | `git status --short -uall` | `git diff` | `git diff --cached` |
| --- | --- | --- | --- |
| 未跟踪新文件 / Untracked new file | `?? new.py` | 无输出 / Empty | 无输出 / Empty |
| 已跟踪、未暂存修改 / Tracked, unstaged change | `␠M tracked.py` | 显示修改 / Patch | 无输出 / Empty |
| 已跟踪、已暂存修改 / Tracked, staged change | `M␠ tracked.py` | 无输出 / Empty | 显示修改 / Patch |

表中的 `␠` 代表状态码中的一个空格；下面保留实际输出的空格。暂存区（index）是下一次提交准备采用的内容。普通 `git diff` 查看工作文件与暂存区的差异；`git diff --cached` 查看暂存区与 HEAD 的差异。未跟踪文件没有进入暂存区，本例两种 diff 都看不到它。[官方 git-diff 文档](https://git-scm.com/docs/git-diff)

`␠` marks a space in the two-character status code; the exact spaces are retained below. The index is the content prepared for the next commit. Plain `git diff` compares working files with the index; `git diff --cached` compares the index with HEAD. This untracked file appears in neither diff. [Official git-diff documentation](https://git-scm.com/docs/git-diff)

`--short` 输出简短状态；普通非冲突状态下，第一位是暂存区、第二位是工作区，`??` 表示未跟踪。`-uall` 展开未跟踪目录中的文件，仍不列出被忽略的文件。[官方 git-status 文档](https://git-scm.com/docs/git-status)

`--short` gives compact status. For ordinary non-conflicted tracked paths, the first character describes the index and the second the working tree; `??` means untracked. `-uall` also lists individual files inside untracked directories, while ignored files remain excluded. [Official git-status documentation](https://git-scm.com/docs/git-status)

## 三个最小复现 / Three minimal reproductions

以下完整命令在子 shell 内创建临时目录，运行完只清除该临时目录。每个状态都有自己的仓库，初始文件均为 `answer = 1`。暂存案例仅对刚创建的演示文件执行 `git add -- tracked.py`，不是对用户项目批量暂存。

This complete script creates a temporary directory inside a subshell and removes that directory on exit. Each state gets its own repository with `answer = 1` as the baseline. Staging is limited to the known demo file, using `git add -- tracked.py`.

```bash
(
  set -eu
  rise_demo=$(mktemp -d "${TMPDIR:-/tmp}/rise-git-review.XXXXXX")
  trap 'rm -rf -- "$rise_demo"' EXIT
  export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null

  for state in untracked unstaged staged; do
    mkdir "$rise_demo/$state"
    cd "$rise_demo/$state"
    git init -q --template=
    git config --local core.hooksPath /dev/null
    git config --local color.ui false
    git config --local user.name 'RISE Demo'
    git config --local user.email 'demo@example.invalid'
    printf 'answer = 1\n' > tracked.py
    git add -- tracked.py
    git commit -qm baseline

    case "$state" in
      untracked) printf 'answer = 2\n' > new.py ;;
      unstaged)  printf 'answer = 2\n' > tracked.py ;;
      staged)
        printf 'answer = 2\n' > tracked.py
        git add -- tracked.py
        ;;
    esac

    printf '\n[%s] status\n' "$state"
    git status --short -uall
    printf '[%s] diff\n' "$state"
    git diff
    printf '[%s] cached\n' "$state"
    git diff --cached
    if [ "$state" = untracked ]; then
      printf '[untracked] read new.py\n'
      cat -- new.py
    fi
  done
)
```

精确命令输出（`diff`/`cached` 标题紧接下一标题，表示该命令没有输出）：

Exact command output (adjacent headings mean the intervening command produced no output):

```text
[untracked] status
?? new.py
[untracked] diff
[untracked] cached
[untracked] read new.py
answer = 2

[unstaged] status
 M tracked.py
[unstaged] diff
diff --git a/tracked.py b/tracked.py
index 3ee5ee9..8dda3ea 100644
--- a/tracked.py
+++ b/tracked.py
@@ -1 +1 @@
-answer = 1
+answer = 2
[unstaged] cached

[staged] status
M  tracked.py
[staged] diff
[staged] cached
diff --git a/tracked.py b/tracked.py
index 3ee5ee9..8dda3ea 100644
--- a/tracked.py
+++ b/tracked.py
@@ -1 +1 @@
-answer = 1
+answer = 2
```

## 用在真实审查 / Apply it during review

先看 `git status --short -uall`，再分别读 `git diff` 和 `git diff --cached`。对 `??` 标记的新文件，按路径逐个打开阅读全文；上例使用 `cat -- new.py`。确认用途、内容和是否应纳入版本控制后，再决定是否暂存具体文件。不要为了让 diff 出现而直接执行 `git add .`。这套步骤覆盖本例三种状态，不替代测试或被忽略文件、合并冲突、子模块的专门检查。

Read `git status --short -uall`, then inspect both `git diff` and `git diff --cached`. Open each `??` file individually and read its contents; the example uses `cat -- new.py`. Decide whether to stage a specific file after reviewing its purpose and content. Do not run `git add .` merely to make a diff appear. These steps cover the three demonstrated states; tests and separate checks for ignored files, merge conflicts, and submodules still matter.

## X 内容草稿 / X discussion drafts

发布前核对账号授权、实际运行结果与字数；这两段是草稿，没有声称已经发帖。

Check account authorization, reproduction results, and post length before publishing. These are drafts, not evidence of publication.

**中文**

> AI 写完代码，git diff 为空，不一定审完了。刚在临时仓库复现：未跟踪新文件，diff 和 cached 都空；修改已暂存，普通 diff 也空。我的检查顺序：status --short -uall → diff → diff --cached → 逐个读新文件。你漏审过哪一种？来源：https://git-scm.com/docs/git-diff （Codex，经授权）

**English**

> Empty git diff? My local repro found two blind spots: untracked files, and changes already staged. Review: status --short -uall → diff → diff --cached → read each new file. Which caught you? https://git-scm.com/docs/git-diff (Codex, authorized)

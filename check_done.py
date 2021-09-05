from subprocess import run
from sys import argv
import re 

# Crawl files in the given directory and return a set of matched Youtube ID 
# from their filenames.

cmd = [
        "find", argv[1], 
        # "-type", "f", r"\(", "-iname", "'*.mkv'", "-o", "-iname", "'*.mp4'", "-printf", r"\)", r"%f\n", 
        "-type", "f", 
        "-iregex", r'.*\.\(mkv\|mp4\|opus\|m4a\)', "-printf", r"%f\n",
        # "|", "sed", "-n", r's/^.*\][\s_]\?\(.*\)\..\{3\}$/\1/p'
    ]

print(f"cmd: {cmd}")

proc = run(
    cmd,
    # shell=True,
    check=False,
    capture_output=True, # stdout=DEVNULL, stderr=DEVNULL
    # stdout=PIPE,
    text=True
)

youtube_id_re = re.compile(r'.*\][\s_]?(.*)\..{3}', re.IGNORECASE)

def find_youtube_id(file_list: list) -> set:
    ids = set()
    for fname in file_list:
        match = youtube_id_re.match(fname)
        if match:
            group = match.group(1)
            ids.add(group)
    return ids

def sort_output(output: str) -> tuple[list, int]:
    line_count = 0
    filenames = []
    for line in output.split('\n'):
        line = line.rstrip()
        if len(line) > 0:
            line_count += 1
            filenames.append(line)
    filenames.sort()
    return filenames, line_count


filenames, count = sort_output(proc.stdout)
print(f"Total files found: {count}")

ids = find_youtube_id(filenames)
print(f"IDs found ({len(ids)}): ")
for id in ids:
    print(id)
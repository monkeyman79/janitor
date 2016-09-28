
python
import sys
import os
if not "janitor_added" in locals():
    sys.path.append(os.environ['HOME'] + '/git/janitor/python')
    janitor_added = True
import janitor.commands
import janitor.functions
end

set $janitor_loaded = 0
define start-janitor
    if ! $janitor_loaded
        source ~/git/janitor/janitor.gdb
        set $janitor_loaded = 1
    end
end


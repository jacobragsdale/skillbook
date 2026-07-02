SERVER := 100.103.224.99

# Voice skills ride git, not rsync (D8 in the jarvis repo): the server's
# ~/jarvis-skills is a real clone that jarvis itself commits to (learnings
# to main, new skills to the `jarvis` branch), so deploy = push + pull.
# Pull first: jarvis may have pushed learnings since our last sync.
deploy:
	git pull --rebase origin main
	git push origin main
	ssh $(SERVER) 'git -C ~/jarvis-skills pull --ff-only \
		&& bash ~/jarvis-skills/scripts/install-server.sh'

# Post-hoc review: jarvis commits straight to main (author "jarvis").
review-jarvis:
	git pull --rebase origin main
	git log --author=jarvis --oneline -15
	@echo "(git show <sha> for any of the above)"

.PHONY: deploy review-jarvis

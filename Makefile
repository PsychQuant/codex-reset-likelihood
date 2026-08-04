# codex-reset-likelihood — deployment
#
# The site is a single static index.html; there is no build step. Everything
# here wraps the Vercel CLI so the deploy is reproducible from one command and
# nobody has to remember the scope flag.
#
#   make check      run the pre-deploy gate
#   make preview    deploy a preview URL
#   make deploy     run the gate, then deploy to production
#
# Override the target team/project on the command line if needed:
#   make deploy SCOPE=some-other-team

SCOPE   ?= psych-quant
PROJECT ?= codex-reset-likelihood
ORG     ?= PsychQuant

.DEFAULT_GOAL := help

.PHONY: help check link preview deploy verify unprotect open logs shot clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-10s\033[0m %s\n", $$1, $$2}'

check: ## Pre-deploy gate — fails loudly rather than shipping something wrong
	@fail=0; \
	test -f index.html || { echo "FAIL  index.html missing"; fail=1; }; \
	test -f vercel.json || { echo "FAIL  vercel.json missing"; fail=1; }; \
	if grep -q 'kiki830621/codex-reset-likelihood' index.html 2>/dev/null; then \
	  echo "FAIL  index.html still links to the old owner; repo lives under $(ORG)"; fail=1; fi; \
	if grep -qE 'TODO|FIXME|XXX' index.html 2>/dev/null; then \
	  echo "FAIL  index.html contains TODO/FIXME"; fail=1; fi; \
	if ! grep -q 'SYNTHETIC DATA' index.html 2>/dev/null && \
	   ! grep -qi 'synthetic' index.html 2>/dev/null; then \
	  echo "FAIL  synthetic-data disclosure is missing — every figure is fabricated"; fail=1; fi; \
	command -v vercel >/dev/null || { echo "FAIL  vercel CLI not installed"; fail=1; }; \
	vercel whoami >/dev/null 2>&1 || { echo "FAIL  not logged in — run: vercel login"; fail=1; }; \
	if [ $$fail -eq 0 ]; then echo "OK    ready to deploy as $(ORG)/$(PROJECT)"; else exit 1; fi

link: ## Link this directory to the Vercel project (one-off)
	vercel link --scope $(SCOPE) --project $(PROJECT) --yes

preview: check ## Deploy a preview URL
	vercel deploy --scope $(SCOPE) --yes

deploy: check ## Deploy to production, then confirm the public can actually reach it
	vercel deploy --prod --scope $(SCOPE) --yes
	@$(MAKE) --no-print-directory verify

verify: ## Confirm production returns 200 to an anonymous visitor
	@url=$$(vercel ls --scope $(SCOPE) 2>/dev/null \
	  | grep -oE 'https://[a-z0-9.-]+\.vercel\.app' | head -1); \
	test -n "$$url" || { echo "FAIL  no deployment URL found"; exit 1; }; \
	code=$$(curl -s -o /dev/null -w '%{http_code}' "$$url"); \
	if [ "$$code" = "200" ]; then \
	  echo "OK    $$url is publicly reachable (200)"; \
	elif [ "$$code" = "307" ] || [ "$$code" = "302" ]; then \
	  echo "FAIL  $$url returns $$code — Vercel Authentication is on, so"; \
	  echo "      anonymous visitors get bounced to an SSO login page."; \
	  echo "      A deployment can report READY and still be invisible."; \
	  echo "      Fix: make unprotect"; exit 1; \
	else \
	  echo "FAIL  $$url returned $$code"; exit 1; fi

unprotect: ## Disable Vercel Authentication (this site is meant to be public)
	@pid=$$(python3 -c "import json;print(json.load(open('.vercel/project.json'))['projectId'])"); \
	echo '{"ssoProtection":null}' \
	  | vercel api "/v9/projects/$$pid" -X PATCH --input - --scope $(SCOPE) --silent \
	  && echo "OK    Vercel Authentication disabled for $(PROJECT)"

open: ## Open the project dashboard
	vercel open --scope $(SCOPE)

logs: ## Tail the latest deployment's logs
	vercel logs --scope $(SCOPE)

shot: ## Screenshot the local page at desktop and mobile widths
	@command -v agent-browser >/dev/null || { echo "agent-browser not installed"; exit 1; }
	agent-browser set viewport 1440 900
	agent-browser open "file://$(CURDIR)/index.html"
	agent-browser screenshot /tmp/crl-desktop.png
	agent-browser set viewport 390 844
	agent-browser open "file://$(CURDIR)/index.html"
	agent-browser screenshot /tmp/crl-mobile.png
	@echo "wrote /tmp/crl-desktop.png and /tmp/crl-mobile.png"

clean: ## Remove local Vercel state
	rm -rf .vercel

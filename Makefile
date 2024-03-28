.PHONY: install start enable status

install:
	sudo cp login_collect_bot.service /etc/systemd/system/
	sudo systemctl daemon-reload

nano:
	nano .env
start:
	sudo systemctl start login_collect_bot

enable:
	sudo systemctl enable login_collect_bot

status:
	sudo systemctl status login_collect_bot

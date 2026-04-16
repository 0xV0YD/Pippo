up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f telegram-bot

restart:
	docker compose down
	docker compose up -d --build

stop:
	docker compose down

build-meeting-chunks:
	python cli/build_meeting_chunks.py

build-meeting-embeddings:
	python cli/build_meeting_embeddings.py

retrieve-meetings:
	python cli/retrieve_meetings.py "$(query)"

answer-meetings:
	python cli/answer_meetings.py "$(query)"

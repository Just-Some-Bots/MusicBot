.PHONY: build push test

IMAGE := xnaveira/musicbot
ENV_FILE := environment.env

build:
	docker build -t $(IMAGE) .

push: image
	docker push $(IMAGE)

test: build
	docker run --env-file $(ENV_FILE) $(IMAGE)

# PrairieLearn Interactive Workspace

To build the GDB demo image, run `docker build -t andylizf/gdb-service .` in the `gdb-image` directory. For you, you need to change the `andylizf` to your Docker username, and also **change the image name in the questions/gdb/info.json file to your username**.

To run the PrairieLearn container, run the following command:

```bash
docker run -it --rm -p 3000:3000 -v ".:/course" -v "$HOME/pl_ag_jobs:/jobs" -e `
HOST_JOBS_DIR="$HOME/pl_ag_jobs" -v /var/run/docker.sock:/var/run/docker.sock `
--platform linux/amd64 --add-host=host.docker.internal:172.17.0.1 `
prairielearn/prairielearn
```

> For some reasons, the docker-compose file does not work. And use `gdb-service` local image does not work either. So now we need to use our own Docker image, change the `info.json` file to use our image, and run the above command. Maybe you can find a way to fix the docker-compose file later.

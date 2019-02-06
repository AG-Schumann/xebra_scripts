# Scripts to help with Xebra analysis

Put stuff here that you use so others can use it as well.

## Jupyter setup

0. Connect to the remote machine (Doberman, Monster, etc).
1. Start a screen session: `$ screen -S <your name here>` and activate the environment you'll be working in: `$ source activate <environment name>`.
2. Start jupyter: `$ jupyter notebook --no-browser --port <port number> --ip <ip address>`. The port number is a 4 or 5 digit number, pick one that someone else isn't using, and the IP address is that of the machine you're connecting to.
3. The jupyter process will give you a login key. We'll use that in a bit.
4. Open a browser on your local machine and point it to `<ip address>:<port number>`. This brings you to the jupyter login screen. It should be asking for a login key
5. Grab the login key that jupyter gave you in Step 3.
6. You should now have access to your jupyter instance running on the remote machine. Voila!
7. Detach from the screen with jupyter (on the remote machine) via `ctrl-a + d`. It'll keep running in the backgroud. Reattach (reconnect) to it with `$ screen -x <your name here>`. If you try to open another jupyter on the same port number, things will break. Don't do it. If you try to run multiple jupyters on the same machine and access the same notebooks, things will break. Don't do it.
8. When you're done with whatever you were doing, stop your jupyter to free the resources for others. Reattach to the screen (see Step 7) and kill it with `ctrl-c`.

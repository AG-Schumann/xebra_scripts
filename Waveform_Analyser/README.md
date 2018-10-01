# Scripts to help with Xebra analysis

Put stuff here that you use so others can use it as well.

## Jupyter setup

0. Connect to the remote machine (Doberman, Monster, etc).
1. Start a screen session: `$ screen -S <your name here>` and activate the environment you'll be working in: `$ source activate <environment name>`.
2. Start jupyter: `$ jupyter notebook --no-browser --port <port number>`. The port number is a 4 or 5 digit number, pick one that someone else isn't using.
3. The jupyter process will give you a login key. We'll use that in a bit.
4. On your local machine, open an ssh tunnel to the remote machine: `$ ssh -N -f -L localhost:<port number>:localhost:<port number> username@host` where `<port number>` is the number you chose in Step 2 and `username@host` is how you connect to the remote machine.
5. Open a browser on your local machine and point it to `localhost:<port number>`. This brings you to the jupyter login screen. It should be asking for a login key
6. Grab the login key that jupyter gave you in Step 3.
7. You should now have access to your jupyter running on the remote machine. Voila!
8. Detach from the screen with jupyter via `ctrl-a + d`. It'll keep running in the backgroud. Reattach (reconnect) to it with `$ screen -x <your name here>`. If you try to open another jupyter on the same port number, things will break. Don't do it.
9. When you're done with whatever you were doing, close your jupyter to free the resources for others. Reattach to the screen (see Step 8) and kill it with `ctrl-c`.

## How to pax

0. Activate the pax environment: `$ source activate pax`
1. Call pax via `$ paxer --config <config file name> --input <path to input> --output <path to output>`.

Notes:
- Config file name: this is the name of the config file you're using. This tells pax what you want to do. The `.ini` isn't necessary.
- Path to input: the path to the input data. If you're specifying zipped waveforms, do not include the trailing `/`.
- Path to putput: where you want the output data to go. You don't need to specify the extension.

import subprocess
import tempfile

def echidna_exists():
    return subprocess.call(['/usr/bin/env', 'echidna', '--help'], stdout=subprocess.PIPE) == 0

def stack_exists():
    return subprocess.call(['/usr/bin/env', 'stack', '--help'], stdout=subprocess.PIPE) == 0

def git_exists():
    return subprocess.call(['/usr/bin/env', 'git', '--version'], stdout=subprocess.PIPE) == 0

def install_echidna(allow_reinstall = False):
    if not allow_reinstall and echidna_exists():
        return
    elif not git_exists():
        raise Exception('Git must be installed in order to install Echidna')
    elif not stack_exists():
        raise Exception('Haskell Stack must be installed in order to install Echidna. On OS X you can easily install it using Homebrew: `brew install haskell-stack`')

    with tempfile.TemporaryDirectory() as path:
        subprocess.check_call(['/usr/bin/env', 'git', 'clone', 'https://github.com/trailofbits/echidna.git', path])
        # TODO: Once the `dev-no-hedgehog` branch is merged into `master`, we can remove this:
        subprocess.call(['/usr/bin/env', 'git', 'checkout', 'dev-no-hedgehog'], cwd=path)
        subprocess.check_call(['/usr/bin/env', 'stack', 'install'], cwd=path)

if __name__ == '__main__':
    install_echidna(allow_reinstall = True)

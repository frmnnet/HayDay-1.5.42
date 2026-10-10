import re
import sys
import zipfile

URL = re.compile(rb'http://[^\x00/]+/+env_settings\?[^\x00]*')


def patch(data, host, port):
    origin = 'http://{}:{}'.format(host, port).encode()
    count = 0

    def sub(m):
        nonlocal count
        old = m.group(0)
        tail = old[old.index(b'env_settings'):]
        pad = len(old) - len(origin) - len(tail)
        if pad < 1:
            sys.exit('host too long for {!r} (max {} chars incl. port)'.format(old, len(old) - len(tail) - 8))
        count += 1
        return origin + b'/' * pad + tail

    data = URL.sub(sub, data)
    return data, count


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    src, dst, host = sys.argv[1:4]
    port = sys.argv[4] if len(sys.argv) > 4 else '8080'
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
        for i in zi.infolist():
            data = zi.read(i.filename)
            if i.filename.endswith('.app/Hay Day'):  # main executable
                data, n = patch(data, host, port)
                if n != 3:
                    sys.exit('expected 3 env_settings URLs, patched {}'.format(n))
                print('patched {} URLs http://{}:{}'.format(n, host, port))
            zo.writestr(i, data)
    print('ipa:', dst)


if __name__ == '__main__':
    main()

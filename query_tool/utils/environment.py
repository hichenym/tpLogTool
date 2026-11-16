ENVIRONMENTS = ('pro', 'test')


def normalize_environment(env):
    value = str(env or 'pro').strip().lower()
    if value not in ENVIRONMENTS:
        raise ValueError(f'不支持的平台: {value}')
    return value


def environment_label(env):
    return '测试平台' if normalize_environment(env) == 'test' else '正式平台'


def console_host(env):
    return 'console-test.seetong.com' if normalize_environment(env) == 'test' else 'console.seetong.com'


def cloud_endpoints(env):
    base = 'https://console-test.seetong.com/api' if normalize_environment(env) == 'test' else 'https://app-auth.seetong.com'
    return f'{base}/seetong-member-auth/oauth/token', f'{base}/seetong-client/client/access-node'

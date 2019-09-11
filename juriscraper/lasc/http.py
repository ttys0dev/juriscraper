import requests

from lxml.html import fromstring

from ..lib.log_tools import make_default_logger

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning)

logger = make_default_logger()


class LASCSession(requests.Session):
    """
    A requests.Session object with special tooling to handle the Los Angeles
    Superior Court Media Access portal.
    """

    def __init__(self, username=None, password=None):
        """
        Instantiate a new LASC HTTP Session with some Juriscraper defaults.
        This method requires credentials from the media access portal.

        :param username: MAP username
        :param password: MAP password
        :return: A LASCSession object
        """
        super(LASCSession, self).__init__()

        self.html = None

        # Los Angeles Superior Court MAP urls and paths
        la_url = 'https://media.lacourt.org'
        self.login_url = '%s/api/Account/Login' % la_url
        self.signin_url = "%s/signin-oidc" % la_url

        # Microsoft urls and paths
        ms_base_url = "https://login.microsoftonline.com"
        api_path1 = "/calcourts02b2c.onmicrosoft.com/B2C_1_Media-LASC-SUSI/SelfAsserted?"
        api_path2 = "/calcourts02b2c.onmicrosoft.com/B2C_1_Media-LASC-SUSI/api/CombinedSigninAndSignup/confirmed?"
        self.api_url1 = "%s%s" % (ms_base_url, api_path1)
        self.api_url2 = "%s%s" % (ms_base_url, api_path2)

        self.login_data = {
            "logonIdentifier": username,
            "password": password,
            "request_type": "RESPONSE"
        }
        self.api_params = {"p": "B2C_1_Media-LASC-SUSI", "tx": ""}
        self.headers = {
            "Origin": ms_base_url,
            "User-Agent": "Juriscraper",
        }

    def get(self, url, auto_login=False, **kwargs):
        """Overrides request.Session.get with session retry logic.

        :param url: url string to GET
        :param auto_login: Whether the auto-login procedure should happen.
        :return: requests.Response
        """
        kwargs.setdefault('timeout', 30)
        return super(LASCSession, self).get(url, **kwargs)

    def post(self, url, auto_login=False, **kwargs):
        """Overrides request.Session.post with session retry logic.

        :param url: url string to GET
        :param auto_login: Whether the auto-login procedure should happen.
        :return: requests.Response
        """
        kwargs.setdefault('timeout', 30)
        return super(LASCSession, self).post(url, **kwargs)

    @staticmethod
    def _parse_html_for_api_parameters(r):
        """
        Parse the HTML after the first login page and identify parameter values
        needed in subsequent requests.

        :param r: A request.Response object
        :return A dict containing parsed parameter values
        :raises: LASCLoginException
        """
        if r.status_code != 200:
            raise LASCLoginException("Got bad status code when attempting "
                                     "initial login: %s" % r.status_code)

        csrf = r.text.split("csrf")[1].split("\"")[2]
        transaction_id = r.text.split("transId")[1].split("\"")[2]
        return {
            'tx': transaction_id,
            'csrf_token': csrf,
            'TRANSID': transaction_id,
        }

    @staticmethod
    def _parse_new_html_for_keys(r):
        """Parse the current page for new key data

        This method parses the HTML after the first login page and identifies
        the parameter values required for the next step.

        :param r: A request.Response object
        :return: A dict containing the needed keys
        """
        html = fromstring(r.text)
        return {
            'code': html.xpath('//*[@id="code"]')[0].value,
            'id_token': html.xpath('//*[@id="id_token"]')[0].value,
            'state': html.xpath('//*[@id="state"]')[0].value,
        }

    @staticmethod
    def check_login(r):
        """Check that the login succeeded

        :param r: A request.Response object
        :return: None
        :raises LASCLoginException
        """
        if r.status_code == 200:
            return

        message = r.json['message']
        if u'Your password is incorrect' in message:
            logger.info(u'Password was incorrect')
            raise LASCLoginException("Invalid username/password")
        if u"We can't seem to find your account" in message:
            logger.info(u'Invalid Email Address')
            raise LASCLoginException("Invalid Email Address")

    def login(self):
        """Log into the LASC Media Access Portal

        The process is tricky, requiring two GET requests, each of which
        returns HTML or JSON that is parsed for values to send in a subsequent
        POST.

        Note that if you do not have media access permissions you can not log
        into the media access portal.

        The individual requests are displayed below for reference.

        The first request
        =================
        First we capture the login page and capture and parse out of the
        TransID and Cross Site Forgery Request token

        curl -X 'GET'
            -H 'Accept: */*'
            -H 'Accept-Encoding: gzip, deflate'
            -H 'Connection: keep-alive'
            -H 'Origin: https://login.microsoftonline.com'
            -H 'User-Agent: Juriscraper'
            'https://login.microsoftonline.com/te/calcourts02b2c.onmicrosoft.com/b2c_1_media-lasc-susi/oauth2/v2.0/authorize?client_id=64f6a02f-a3d7-4871-a7b0-0883a24bdbda&redirect_uri=https%3A%2F%2Fmedia.lacourt.org%2Fsignin-oidc&response_type=code%20id_token&scope=openid%20profile%20offline_access%20https%3A%2F%2Fcalcourts02b2c.onmicrosoft.com%2Fapi%2Fread&response_mode=form_post&nonce=636989032254084125.MWY4YWQxN2UtNDM5MS00ZTc5LThkN2YtMTlhYWZmZjBhZDk5YTVlNDEyMmEtMzI5ZS00YzExLTg4YTMtYmU2MDNhZjgzMWNj&state=CfDJ8Pwr5_ZSA25Lq9tGMhyZSHpY1A9mXEeyoedJD-KgsE5SoZhpEwenEHXOe0PmMbNxFslFGyGgyA4COKS_zqKlJghkVIYO02_amjN6-JOSfcGISf9rY9uqF2yOnwhkda3D00JcU_sOPP6uKexwG87dXvMLaxN6LuCu2GqXGkkAe6fOVKBlzjL8-G_EqX3j0ok8zwUaRJW8D6I4GeCfjg2LJOk4YBmGGmRYYTdCG4usSI1FKYLjhyCVly7aXf__QfHMvCKzVO9tjmK-Sq3REFtCLdPTiBuv1YjE6DlVj6_iUJ_D&x-client-SKU=ID_NET&x-client-ver=2.1.4.0'


        The second request
        ==================
        We make our first POST request to Microsoft's login API and check that
        login credentials were correct.

        curl -X 'POST'
            -H 'Accept: */*'
            -H 'Accept-Encoding: gzip, deflate'
            -H 'Connection: keep-alive'
            -H 'Content-Length: 83'
            -H 'Content-Type: application/x-www-form-urlencoded'
            -H 'Cookie: stsservicecookie=cpim_te; x-ms-gateway-slice=001-000; x-ms-cpim-cache:00ruicnscuqczl9ni9npwg_0=m1.wIcg9B5U2mpN0+In.SAustPP2BSni6Z5+88x2tg==.0.3JkQtcZE7mGmeyqKOwSUXJJY4vWQ2TUI7poxFbEKknCO6oVl+g+z0Zql7fgd0C6o3hOJfqk9DxjTJvkRcSfY6piitXoAQCfsIGnPC5VhVMbyZPPOKyDgRnZpKhxJrutFvdpHWHQ41hBhrxpsJydFaXzdzX9iss8//X6RYfh0Fef6nuP8Qv+OA+THBz8xzzfDF7qJddHZftGKZ2BT/rR6/yOPgeuvuPljYEMsOJfx+KVgyLYBYWSj+JDv7IvGIMfC8AAtuMVFtEE/Hb6ZBBdDbdfnWLd3DtuZkAuqFVeZDbk54mA6E6MQal7zhwhhoqh5Z76+DKNIWBYaehTlRfYyj7qL/mSSctNltg7vzDWVxEUL9z4O6bUACTCBM/Z/yFY6YJCuOBwyXAfJcRJtewDs+MjzcXE0qpe9bXfw4L9290GrzDTgreIAXjuvNBVLtHcb+8v0XqH8MRRnuthwi1/OVtAtoeLsIOBWAGXw9J15wN5qO+PotuBEFVJmbWWZGWtI2ZpMlneBIOCSYBcIKoA/+RuF2GWBzRhvBYZXRYchFA85AJtlmr8ql8yuvMqwkWxICXG5TBjGfJrkDduZSyChaeK9No8mssNjUDMh4wNkaK8bARGRtW7LRnOqOG5E4/dzpjOCNaK+2UEiwc5JfvipNQK30yF9qG0P36Ee35eaBUaHwfaAH0MM/YaKrX8SXt3Xco2w60rlpqTfYxloabR96v8dxbQxFJETB9HG4cS4A5e9jJ/FJTHYk0VXFIHJn3uCgSmI4Y4eZUmV58yCfEZo8ICBXbZSCRjOQROfpCklcrI0EFkj1zk/PhHntpUAXct6BcNdu7RcmAnlqgkfusUEmij7RcXjB2TNZAaqA3Pzkyk5dBOlAPXtqjKfhBHbLJLeUDdAwneMyEtZzzmKZFK2w685VwvJVw6NejnULArwwwXPq7G//ROYBdmLt91b8Fabq9d0UMB4S2TN8zz1ebtUWqKzrNKgf3bqyTm/B8mNuhjRtfKYMEkq/CZBeTbAzibyCfkjRNOjjYz1bg94Zed3T0NUT4wCCckx+HrwfsEFlwd99Xh9+IaKuaE88vAFNp7EEm/aFdoRmTCyNRgJTsT8d/R/F7SoUag=; x-ms-cpim-trans=eyJUX0RJQyI6W3siSSI6Ijg5ZWU0YWQzLTZjYzMtNGE3MS05YzY2LTVmNjcyM2Q5Y2ZjMiIsIlQiOiJjYWxjb3VydHMwMmIyYy5vbm1pY3Jvc29mdC5jb20iLCJQIjoiYjJjXzFfbWVkaWEtbGFzYy1zdXNpIiwiQyI6IjY0ZjZhMDJmLWEzZDctNDg3MS1hN2IwLTA4ODNhMjRiZGJkYSIsIlMiOjEsIk0iOnt9LCJEIjowfV0sIkNfSUQiOiI4OWVlNGFkMy02Y2MzLTRhNzEtOWM2Ni01ZjY3MjNkOWNmYzIifQ==; x-ms-cpim-csrf=MG9tTzRzUTNRWjlaTEVUOG1TT1RsN0w5dTdMdTM4RHpwUGlHcEJwTmxudkNTUXE3T3RGQzNkVEJrRHVrTzc5OEcrM2VSWnlUZ3hyNzJtQUJWYTVnN1E9PTsyMDE5LTA3LTE2VDE5OjQ5OjE4LjQyMjExOTlaO2kzMjhnTURMQ0NuYytZTGRCdDVjRWc9PTt7Ik9yY2hlc3RyYXRpb25TdGVwIjoxfQ==' -H 'Origin: https://login.microsoftonline.com' -H 'User-Agent: Juriscraper' -H 'X-CSRF-TOKEN: MG9tTzRzUTNRWjlaTEVUOG1TT1RsN0w5dTdMdTM4RHpwUGlHcEJwTmxudkNTUXE3T3RGQzNkVEJrRHVrTzc5OEcrM2VSWnlUZ3hyNzJtQUJWYTVnN1E9PTsyMDE5LTA3LTE2VDE5OjQ5OjE4LjQyMjExOTlaO2kzMjhnTURMQ0NuYytZTGRCdDVjRWc9PTt7Ik9yY2hlc3RyYXRpb25TdGVwIjoxfQ=='
            -d 'request_type=RESPONSE&password={{PASSWORD}}&logonIdentifier={{USERNAME}}'
            'https://login.microsoftonline.com/calcourts02b2c.onmicrosoft.com/B2C_1_Media-LASC-SUSI/SelfAsserted?p=B2C_1_Media-LASC-SUSI&csrf_token=MG9tTzRzUTNRWjlaTEVUOG1TT1RsN0w5dTdMdTM4RHpwUGlHcEJwTmxudkNTUXE3T3RGQzNkVEJrRHVrTzc5OEcrM2VSWnlUZ3hyNzJtQUJWYTVnN1E9PTsyMDE5LTA3LTE2VDE5OjQ5OjE4LjQyMjExOTlaO2kzMjhnTURMQ0NuYytZTGRCdDVjRWc9PTt7Ik9yY2hlc3RyYXRpb25TdGVwIjoxfQ%3D%3D&TRANSID=StateProperties%3DeyJUSUQiOiI4OWVlNGFkMy02Y2MzLTRhNzEtOWM2Ni01ZjY3MjNkOWNmYzIifQ&tx=StateProperties%3DeyJUSUQiOiI4OWVlNGFkMy02Y2MzLTRhNzEtOWM2Ni01ZjY3MjNkOWNmYzIifQ'

        The third request
        =================
        The third request handles a redirect request that is required by the
        system. And we generate the parameters we need for the final request.

        curl -X 'GET'
            -H 'Accept: */*'
            -H 'Accept-Encoding: gzip, deflate'
            -H 'Connection: keep-alive'
            -H 'Cookie: stsservicecookie=cpim_te; x-ms-gateway-slice=001-000; x-ms-cpim-trans=eyJUX0RJQyI6W3siSSI6IjlkNDk3MjUwLTdkZjMtNGIwYS1hNjk3LWJlZDYwOTAzMDk5MiIsIlQiOiJjYWxjb3VydHMwMmIyYy5vbm1pY3Jvc29mdC5jb20iLCJQIjoiYjJjXzFfbWVkaWEtbGFzYy1zdXNpIiwiQyI6IjY0ZjZhMDJmLWEzZDctNDg3MS1hN2IwLTA4ODNhMjRiZGJkYSIsIlMiOjIsIk0iOnt9LCJEIjowfV0sIkNfSUQiOiI5ZDQ5NzI1MC03ZGYzLTRiMGEtYTY5Ny1iZWQ2MDkwMzA5OTIifQ==; x-ms-cpim-cache:uhjjnfn9ckuml77wcqmjkg_0=m1.4Df4p+alIR6v2hGl.ITZLREieC04EqRrl9BxyeA==.0.xxHdeSM8OJh9vSWkTVzzh9fpDr2udaIBKcOOtgm3FpDThaLLlir9XIYMKVF4CkRX18HZKbxr3bv9Kwgm9ic/R1/g/y1nQRp9T9V7XNyHr/vemalGjeAgdhPpFnwfbDZm9NVPdTEkN71HYbkJV56dlq+zpG6U9Z4Nm4jT6NWlBmeLDoErgACZ9BUJXO5EPWEmLnyrqlMZeK0qB4cnYBvyoa9hFvkJvhKNsmFlrvD1KutuzuaBQShOjSGdsqbrnNCvQQWwrHaCrhXBV5oG03aLUjpKk8Tg4mV21C4U5h9tQxHtq5a+WB/fowLhkQ+3ZY5b3lKHds0rGHH0CRpS9juyJ9peGCiNdsdM6HVGDCCmg+wW/Hs6f/OOba4QBcNMVATe4cAZ1xxd8vOjXnQnkrTGuuKmOXEXRve6i+Y70x8T9I6S2nmGagSn3wVcc5IEZRLEksb/u76hIQjdGPdwWgg8SvM+Gxc68I+8uF5BGrzNbK6s7JHus9IS3p3J5zfT3fyXVrmHWkpsVMN0Pkyblt8CNHw0vRRx14iE17Kd9iV7c2OYS7c6lfuAaI2I75cdtYYiXghExOxUm1WgfYGf4LXXWSj9xNfhf35N4DvrMsK+3maegA4gAHs86oIEueGyDYFxPe8hJOyhX956C0JDjGkp+eqHwxB9dmkLSmeLBxhvGdDkr2o9zy/Ovs0T6TdJvAQf9AwUz6uNPa90heBbJKbPptrrWFFBxx/2a/R8u+Ca0g4Udicn61evtugkwf0hWYgb3sBLZmDKoQAJJ9zt+qM99JWhmkCyoRc7xU9YPB+jTl4HpmUaO4PW6Vg1VbQZMR6eFvZoYQTiJbAdNkl8W65hjzByrZ0G6bhgBK7oClHLbRwMIlXlv+dUV0EQi23FYWnMtvoSDYWRjmdXEgJRAukNhfsYLyUxYhAJVIO3M//609Qydo5WMeYeXDYvGMDv2YV7nmGC0VJ/JYxJ0c3nZP4IagztZ+21CTyab1vChr+hDsrpzmHkLENIS8HFqT+1vAWF4GxiNrpnQo8nFnsy/SGqezymixfr+FwqpgR6L0Km2l6qVytvdDL9X+x1iAqLFXtO/22+i9T8oK0AQneOEN7ClyKjPS3pmSDRiQOsauVFKQD81egjv0Pn19h+XxPebv4qfnn7bis5lWwKhFdaO8q5wNSDmzotF4Kp52+mmzZutHqSv+bPg683zQuu3THAdy3ANTNlgBFE2f/TIv/cne4OOrkV55HwBHOXVAi8AF5f3l/LmIgHND4CJYgIJSvfvYYYUVwXzsadOQNFvOUTMlC2omxuag==; x-ms-cpim-csrf=QzdLais4SU11S2l0WVBKWGRHOWVyMHFyU0hOcWNlNUJJTkN6MFJ3dnBLdGY1a2VnTW4vZS9jQk9hRnJrU0NHTVZtbEVWWXoxeEZFbFpXQ1FUaXFtZ0E9PTsyMDE5LTA3LTE2VDE5OjUxOjA3LjI4Mjc2OVo7cFkwekVwN0VvMVdQazdYNTc2MkYvQT09O3siT3JjaGVzdHJhdGlvblN0ZXAiOjF9'
            -H 'Origin: https://login.microsoftonline.com'
            -H 'User-Agent: Juriscraper'
            -H 'X-CSRF-TOKEN: QzdLais4SU11S2l0WVBKWGRHOWVyMHFyU0hOcWNlNUJJTkN6MFJ3dnBLdGY1a2VnTW4vZS9jQk9hRnJrU0NHTVZtbEVWWXoxeEZFbFpXQ1FUaXFtZ0E9PTsyMDE5LTA3LTE2VDE5OjUxOjA3LjI4Mjc2OVo7cFkwekVwN0VvMVdQazdYNTc2MkYvQT09O3siT3JjaGVzdHJhdGlvblN0ZXAiOjF9'
            'https://login.microsoftonline.com/calcourts02b2c.onmicrosoft.com/B2C_1_Media-LASC-SUSI/api/CombinedSigninAndSignup/confirmed?p=B2C_1_Media-LASC-SUSI&csrf_token=QzdLais4SU11S2l0WVBKWGRHOWVyMHFyU0hOcWNlNUJJTkN6MFJ3dnBLdGY1a2VnTW4vZS9jQk9hRnJrU0NHTVZtbEVWWXoxeEZFbFpXQ1FUaXFtZ0E9PTsyMDE5LTA3LTE2VDE5OjUxOjA3LjI4Mjc2OVo7cFkwekVwN0VvMVdQazdYNTc2MkYvQT09O3siT3JjaGVzdHJhdGlvblN0ZXAiOjF9&TRANSID=StateProperties%3DeyJUSUQiOiI5ZDQ5NzI1MC03ZGYzLTRiMGEtYTY5Ny1iZWQ2MDkwMzA5OTIifQ&tx=StateProperties%3DeyJUSUQiOiI5ZDQ5NzI1MC03ZGYzLTRiMGEtYTY5Ny1iZWQ2MDkwMzA5OTIifQ'


        The fourth request
        ==================
        The last request finishes the and navigates to the signin page.  We
        submit our credentials and check that we are logged in.

        curl -X 'GET'
            -H 'Accept: */*'
            -H 'Accept-Encoding: gzip, deflate'
            -H 'Connection: keep-alive'
            -H 'Cookie: .AspNetCore.Cookies=CfDJ8Pwr5_ZSA25Lq9tGMhyZSHr8UY6g7hwjNU0XlUHTOl3E8jJL2J9zZCP_M8hPTu9jkTnz48n7Xh04NsryQVtHsekPLasvImDu9vVB9Yh5Q1ZLXcLSLyUbErgz1n6r2c7A9R4DI5BRGz3IM10QxpF9p9Pv9zzWieQUd47LHY2jKXmjdW-ygHMVrLHKVMJuiijm0JsprghvGKm1Poqj8MSOapUeyKbIVtie-2q0RpwiUA-KljZu95-k08d2G33ZHo8ntgLYLY_fgOL2Mz8n038Sa5zSCtlqgxanWmTF5OS7-ijcuYXmdbl8Ln7_uA9181-uJjaKM_qLawemVGPhzSSKG9y0txRyol0UBu6xy7zp2M5QcpJ3ZDU6nVG05RGKd3OjgU5VxXvuNI2kriXiNfzAaJzxhY_vlK7nBccPjGJrF5UlZyfdNUQS9PbDkRmITHQHGYe2HAQBqgIQ7DLq5RzQWK5201_ADnS8Ge_hJk6sb1iv_n8iPjsT28jsEtO0Wlk_Sk3kxabE1NWEOXV8aPesgWw6Yicyn6cu4mR1Bkatm3avewOCUEct7nBDGpcosrR9spOt_vXyjmqI3KbumFtmrLxnR0SjwXBNnsi1uGunjF_Lsan8aprc-CfQr7gHKUGXd3xLz3-3N66G8jbwxRnSeLOnYQ2vykVKFHM_QoA9TBVeJJ4XIHNW0blaIzkeI_X9InJy8-5ZCRJ_2ebKkvbcLC7hEnKVk8PxwyomOMW8CeF8l8MrqDgpXtwLq52L6tU2PJu4gIMSmxDymldDrBoHQDNveMX8P3i85OklGMIH9mRlXZJaJKdLcM3d08MUz7cpB3AjpBLp5LZPP2YLRkJXMF53eZwZDEGi1b1hZDmoUeKAs1ALsE2OwhPZ8YTxSsO9jlylAoZEv-52VCKI-58iq08JJNn27WbFuYumCwaUU3eElhy8BF4XcNdKmdiHHOfrv2Cg3hNqCadPsYejtYApoQ2EYX98e7lhajwrUZTY4ymsge7aq4masSkM468Huah-W4eq7fK5gbBr1vZX0ef9uj6k9RqYJXlOaIN2cl0vamNZvYLHAxWhtP1gHwC0QalRCffOod00z4t3qS3V2Xj7YBBp_uWkjlbM32JKiAWH99pc2C81Xwp2LomaF5JQweS_qawQ7z0l_yIEGAN9DStN3cvGd0lsMZRGvDSWVXQ8IJk0EHkqSmNsQoKsdaaN9FuNM_vLCgdFBKPhgkJTjjsyWAdldOhJAL57AU5x5Ay54nh886sh-94CtuJ5Jd18_yuqKqBsiTa8NV0DbRNl2uYM1MSCs1iYUxyeNY8HI7iyj-Q5kh4WpDQjHhckeT3SLX8PvCEyRctLzhAx__UhTRC-b6xZViCUMaUuLh70ioLBy7hTESQmaciIHDczeQKbfmw70USzj5hRE9oDfjAOTRAMT2FquTuRlVepC3SCQ3Vjqv5j_gjUTGlYcHazbnGY4VSacOQv4az2wE96xXnRL3NoBgN_icp4F-A8YwLmPYJRyK64ouxc2GJPbMEUbJysmCUPYTyCRdoMDszyxc47VJFu-5Zzn-yXab_y5L4Cl_W-Tj105KKgATJLAhwLqQZHBFs4cDTYZ2lhzqEQdKvNyKDrEN_zi-dDvTTF24poPQyWRAlMTgA5I9uZrBof4EXcjad0mISA--RFEseDao5kfzfzPSNHZBgwffIX1bYcxGGfxZ5wGrqg1KCudXnWwSmIuHPlM_uTEGefNBg_dRcaIyif0AnP75hKKA01rdyK48E8UnCrkITXqBdcTy0eYXIHtRCaZNF41nfUCjgIa7MBcpMnfOsHrz-fiKL05DYZmG4MBcX6434QA3srLxXY7u6gsKBj_phEaE5vKYnFt-Oal8JRjjBozrJ7haGhkPSM-of1jj-4dvGLirzObZ716Se2Z8naDL6TriQDj9218T3uRJvwwuXMkwgCSfIAYKWYcBUKKz18IJ8CaloKMPn7QnOlrtfIU0fLoyTsxpBc0T0uIIAu5RELJ6squzUwigR2VkaJ9mhAQ1CvXiR3PTkagP_xt42TifuxnOluf0WyJbXrPg61o4z64GqMSzaEdpf3efI8prfQfx_krXP4gSgKHw5qanPK0ID0-aZ4A1wv2i3gp8mRapYrcmf4Y_VlWSJqEOzm2SSSvM1WvjNevJrQQYPwwXuLIwy8Zi6l8nhd-9PnWBD02R1hjUdTv_VYxoF2nRgP-qMXPeVg99eNfOzJ1wo9pW0gxQ; .AspNetCore.Session=CfDJ8Pwr5%2FZSA25Lq9tGMhyZSHqSUZ1fdAhQfTXbZveNz5Cd4zSPbFO%2FoUukxlHK7LiHmkicHk85LyDx4gO85rjEeUYnoWRnUEeZ3T9%2BWiV7COW%2BuZnAsBHtJDMj%2BX9hzh9STn9tXURw1isdbX4hNBVziHR7695e6oxnwHSbm1tI5ip2' -H 'Origin: https://login.microsoftonline.com' -H 'User-Agent: Juriscraper' -H 'X-CSRF-TOKEN: YlREUUpJUEJMcCtac1UweVVwRDZRM1hIdjVLK1JzL1BVT3d4TFpaR0ZPVkY0dENlMDN0OVBta01IU3E4Vk5iMjhWd1JxVTk1NE4rZy9WUUFOemdXaWc9PTsyMDE5LTA3LTE2VDE5OjUyOjM4LjA5ODYxNzhaO3c2VnJrT1VYYkxkRW5RUURtYmQ5anc9PTt7Ik9yY2hlc3RyYXRpb25TdGVwIjoxfQ=='
            'https://media.lacourt.org/'

        :return: None
        :raises: LASCLoginException
        """
        # Load the page and get the TransID and CSRF Token values from the HTML
        logger.info(u'Logging into MAP has begun')
        r = self.get(self.login_url)

        # Set the CSRF header for subsequent requests
        api_params = self._parse_html_for_api_parameters(r)
        self.headers['X-CSRF-TOKEN'] = api_params['csrf_token']

        # Call part one of Microsoft login API
        r = self.post(self.api_url1, params=api_params, data=self.login_data)
        self.check_login(r)

        # Call part two of Microsoft login API - Redirect
        r = self.get(self.api_url2, params=api_params)

        # Finalize login with post into LA MAP site
        parsed_keys = self._parse_new_html_for_keys(r)
        self.post(self.signin_url, data=parsed_keys)
        logger.info(u'Successfully Logged into MAP')


class LASCLoginException(Exception):
    """
    Raised when the system cannot authenticate with LASC MAP
    """
    def __init__(self, message):
        Exception.__init__(self, message)

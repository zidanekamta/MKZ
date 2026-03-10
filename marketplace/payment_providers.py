import base64
import uuid
import requests


class MtnMomoProvider:
    """
    MTN MoMo Collections:
    - POST /collection/token/ (Basic Auth api_user:api_key) :contentReference[oaicite:2]{index=2}
    - POST /collection/v1_0/requesttopay (X-Reference-Id + X-Callback-Url) :contentReference[oaicite:3]{index=3}
    - GET  /collection/v1_0/requesttopay/{id} :contentReference[oaicite:4]{index=4}
    """

    def __init__(self, base_url: str, subscription_key: str, api_user: str, api_key: str, target_env: str):
        self.base_url = base_url.rstrip("/")
        self.subscription_key = subscription_key
        self.api_user = api_user
        self.api_key = api_key
        self.target_env = target_env

    def _token(self) -> str:
        url = f"{self.base_url}/collection/token/"
        r = requests.post(
            url,
            headers={"Ocp-Apim-Subscription-Key": self.subscription_key},
            auth=(self.api_user, self.api_key),
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data["access_token"]

    def request_to_pay(self, amount: int, currency: str, external_id: str, payer_msisdn: str,
                       payer_message: str, payee_note: str, callback_url: str | None):
        ref_id = str(uuid.uuid4())
        url = f"{self.base_url}/collection/v1_0/requesttopay"

        token = self._token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": ref_id,
            "X-Target-Environment": self.target_env,
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }
        if callback_url:
            headers["X-Callback-Url"] = callback_url

        payload = {
            "amount": str(amount),
            "currency": currency,
            "externalId": external_id,
            "payer": {"partyIdType": "MSISDN", "partyId": payer_msisdn},
            "payerMessage": payer_message,
            "payeeNote": payee_note,
        }

        r = requests.post(url, headers=headers, json=payload, timeout=30)
        # MoMo renvoie souvent 202 Accepted si c'est pris en charge (async) :contentReference[oaicite:5]{index=5}
        if r.status_code not in (200, 201, 202):
            raise RuntimeError(f"MoMo requesttopay failed {r.status_code}: {r.text}")

        return {
            "reference": ref_id,
            "request": payload,
            "response_text": r.text or "",
            "response_status": r.status_code,
        }

    def get_status(self, reference: str):
        url = f"{self.base_url}/collection/v1_0/requesttopay/{reference}"
        token = self._token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": self.target_env,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }
        r = requests.get(url, headers=headers, timeout=30)
        # Certains environnements renvoient parfois sans body, on gère proprement :contentReference[oaicite:6]{index=6}
        if r.status_code not in (200, 202):
            return {"ok": False, "status_code": r.status_code, "text": r.text}
        try:
            return {"ok": True, "data": r.json()}
        except Exception:
            return {"ok": True, "data": None, "text": r.text}


class OrangeMoneyProvider:
    """
    OrangeMoneyCoreAPIS (Cameroun) :
    - POST /mp/init -> payToken
    - POST /mp/pay
    - GET  /mp/paymentstatus/{payToken}
    (host: api-s1.orange.cm, basePath /omcoreapis/1.0.0) :contentReference[oaicite:7]{index=7}

    ⚠️ Le champ "pin" est indiqué dans le swagger. En pratique, utilise le mode/flux recommandé par Orange
    (souvent OTP / confirmation utilisateur), et ne stocke jamais le secret du client.
    """

    def __init__(self, base_url: str, bearer_token: str, x_auth_token: str, channel_msisdn: str):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.x_auth_token = x_auth_token
        self.channel_msisdn = channel_msisdn

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "X-AUTH-TOKEN": self.x_auth_token,
            "Content-Type": "application/json",
        }

    def mp_init(self):
        url = f"{self.base_url}/mp/init"
        r = requests.post(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def mp_pay(self, pay_token: str, subscriber_msisdn: str, amount: int, order_id: str,
               description: str, otp_or_pin: str, notif_url: str | None):
        url = f"{self.base_url}/mp/pay"
        body = {
            "subscriberMsisdn": subscriber_msisdn,
            "channelUserMsisdn": self.channel_msisdn,
            "amount": int(amount),
            "description": description[:120],
            "orderId": str(order_id)[:20],
            "pin": otp_or_pin,
            "payToken": pay_token,
            "notifUrl": notif_url or "",
        }
        r = requests.post(url, headers=self._headers(), json=body, timeout=30)
        r.raise_for_status()
        return {"request": body, "response": r.json()}

    def mp_status(self, pay_token: str):
        url = f"{self.base_url}/mp/paymentstatus/{pay_token}"
        r = requests.get(url, headers=self._headers(), timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status_code": r.status_code, "text": r.text}
        return {"ok": True, "data": r.json()}
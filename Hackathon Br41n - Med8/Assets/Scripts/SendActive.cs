using UnityEngine;
using OscJack;

public class SendActive : MonoBehaviour {
    OscClient client;
    public bool[] active = new bool[6];

    void Start() {
        client = new OscClient("127.0.0.1", 9000);
        InvokeRepeating(nameof(Send), 0f, 0.2f);
    }

    void Send() {
        for (int i = 0; i < active.Length; i++)
            client.Send($"/active/{i}", active[i] ? 1 : 0);
    }
}
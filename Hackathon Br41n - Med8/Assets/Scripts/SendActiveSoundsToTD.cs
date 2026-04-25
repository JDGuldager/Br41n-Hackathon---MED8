using UnityEngine;
using OscJack;
using System.Collections.Generic;

public class SendActiveSoundsToTD : MonoBehaviour
{
    [Header("OSC")]
    [SerializeField] private string host = "127.0.0.1";
    [SerializeField] private int port = 9000;
    [SerializeField] private string oscAddress = "/sounds/active";
    [SerializeField] private float sendInterval = 0.1f;

    [Header("Audio")]
    [SerializeField] private AudioSource[] soundSources = new AudioSource[20];

    private OscClient client;
    private int[] lastSent = { -999, -999, -999, -999 };

    void Start()
    {
        client = new OscClient(host, port);
        InvokeRepeating(nameof(CheckAndSend), 0f, sendInterval);
    }

    void CheckAndSend()
    {
        List<int> activeIndices = new List<int>(4);

        for (int i = 0; i < soundSources.Length; i++)
        {
            if (soundSources[i] != null && soundSources[i].isPlaying)
            {
                activeIndices.Add(i);

                if (activeIndices.Count == 4)
                    break;
            }
        }

        while (activeIndices.Count < 4)
            activeIndices.Add(-1);

        bool changed = false;
        for (int i = 0; i < 4; i++)
        {
            if (activeIndices[i] != lastSent[i])
            {
                changed = true;
                break;
            }
        }

        if (changed)
        {
            client.Send(
                oscAddress,
                activeIndices[0],
                activeIndices[1],
                activeIndices[2],
                activeIndices[3]
            );

            for (int i = 0; i < 4; i++)
                lastSent[i] = activeIndices[i];
        }
    }

    void OnDestroy()
    {
        CancelInvoke(nameof(CheckAndSend));
        client?.Dispose();
    }
}
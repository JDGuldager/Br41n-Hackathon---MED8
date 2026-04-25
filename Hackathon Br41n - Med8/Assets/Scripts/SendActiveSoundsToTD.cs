using System.Collections.Generic;
using UnityEngine;
using OscJack;

public class SendActiveSoundsToTD : MonoBehaviour
{
    [Header("References")]
    public CDSelectionManager selectionManager;

    [Header("OSC")]
    public string host = "127.0.0.1";
    public int port = 9000;
    public string oscAddress = "/sound/active";
    public float sendInterval = 0.1f;

    [Header("CD Order")]
    public List<string> allCDNames = new List<string>(20);

    private OscClient client;
    private int[] lastSent = { -999, -999, -999, -999 };

    void Start()
    {
        client = new OscClient(host, port);
        InvokeRepeating(nameof(CheckAndSend), 0f, sendInterval);
    }

    void CheckAndSend()
    {
        if (selectionManager == null) return;

        List<int> activeIds = new List<int>();

        foreach (string cdName in selectionManager.selectedCDs)
        {
            int id = allCDNames.IndexOf(cdName);
            if (id >= 0)
                activeIds.Add(id);
            else
                Debug.LogWarning("CD name not found in allCDNames: " + cdName);
        }

        while (activeIds.Count < 4)
            activeIds.Add(-1);

        if (activeIds.Count > 4)
            activeIds = activeIds.GetRange(0, 4);

        bool changed = false;
        for (int i = 0; i < 4; i++)
        {
            if (activeIds[i] != lastSent[i])
            {
                changed = true;
                break;
            }
        }

        if (changed)
        {
            client.Send(oscAddress, activeIds[0], activeIds[1], activeIds[2], activeIds[3]);

            for (int i = 0; i < 4; i++)
                lastSent[i] = activeIds[i];

            Debug.Log($"Sent CDs: {activeIds[0]}, {activeIds[1]}, {activeIds[2]}, {activeIds[3]}");
        }
    }

    void OnDestroy()
    {
        CancelInvoke(nameof(CheckAndSend));
        client?.Dispose();
    }
}
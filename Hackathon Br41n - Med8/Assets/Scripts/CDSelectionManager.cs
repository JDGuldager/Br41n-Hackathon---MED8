using System.Collections.Generic;
using UnityEngine;

public class CDSelectionManager : MonoBehaviour
{
    [Header("References")]
    public JukeboxWheel jukeboxWheel;

    [Header("Settings")]
    public int maxSelectedCDs = 4;

    [Header("Selected CDs")]
    public List<string> selectedCDs = new List<string>();

    public void ToggleCurrentCD()
    {
        if (jukeboxWheel == null) return;

        Transform currentCD = jukeboxWheel.GetSelectedCD();
        if (currentCD == null) return;

        string cdName = currentCD.name;

        if (selectedCDs.Contains(cdName))
        {
            selectedCDs.Remove(cdName);
            Debug.Log("Unselected CD: " + cdName);
            return;
        }

        if (selectedCDs.Count >= maxSelectedCDs)
        {
            Debug.Log("Maximum selected CDs reached.");
            return;
        }

        selectedCDs.Add(cdName);
        Debug.Log("Selected CD: " + cdName);
    }

    public bool IsSelected(Transform cd)
    {
        if (cd == null) return false;
        return selectedCDs.Contains(cd.name);
    }
}
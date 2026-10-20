using UnityEngine;

//[RequireComponent(typeof(Collider2D), typeof(DialogueViewer))]
public class Chest : InteractableObject
{
    [SerializeField] private Key _neededKey;
    [SerializeField] DialogueViewer _insideInformation;

    private void OnEnable()
    {
        _isInteractable = false;

        _neededKey.OnKeyCollected += GetInteractable;
    }

    private void OnDisable()
    {
        _neededKey.OnKeyCollected -= GetInteractable;
    }

    public override void Interact()
    {
        if (_isInteractable)
        {
            StartCoroutine(_insideInformation.Starter());
            Deselect();
            _isInteractable = false;
        }
    }

    private void GetInteractable()
    {
        _isInteractable = true;
    }
}

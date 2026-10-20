using System;

public class Key : InteractableObject
{
    public event Action OnKeyCollected;

    public override void Interact()
    {
        OnKeyCollected?.Invoke();
        OnKeyCollected = null;
        Destroy(gameObject);
    }
}

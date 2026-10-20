using UnityEngine;


public class InteractableObject : MonoBehaviour
{
    
    [SerializeField] protected GameObject _interactiveSign;
    protected bool _isInteractable = true;
    
    
    private void Start()
    {
        _interactiveSign.SetActive(false);
    }

    public virtual void Interact()
    {
        Debug.Log("Parent's Interact");
    }

    public virtual bool TrySelect()
    {
        if (_isInteractable)
        {
            _interactiveSign.SetActive(true);
        }
        
        return _isInteractable;
    }

    public virtual void Deselect()
    {
        _interactiveSign.SetActive(false);
    }

    public void SetInteractable(bool isInteractable)
    {
        _isInteractable = isInteractable;
    }
}

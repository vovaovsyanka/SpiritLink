using System.Collections.Generic;
using UnityEngine;

public class DialogueCharacter : InteractableObject
{
    [System.Serializable]
    public struct SetAnimParameter
    {
        public string boolParameterName;
        public bool BoolParameterInput;
        [Space(10)]
        [HideInInspector]public TypeOfDialogue typeOfDialogue;
        [Multiline]public string inputText;

    }

    [SerializeField] private Animator _animator;
    [SerializeField] private DialogueViewer _dialogueViewer;
    [SerializeField] private Collider2D _triggerCollider;
    [Space(10)]
    [SerializeField] private List<SetAnimParameter> _setAnimParameters;
    
    private void Update()
    {

        if (!_dialogueViewer.IsCurrentViewerActive() || _setAnimParameters.Count == 0 || _animator == null || _setAnimParameters.Count == 0)
        {
            return;
        }

        Deselect();
        foreach( SetAnimParameter setAnimParameter in _setAnimParameters)
        {
            if(setAnimParameter.typeOfDialogue == _dialogueViewer.CurrentDialogueElement.TypeOfDialogue && setAnimParameter.inputText == _dialogueViewer.CurrentDialogueElement.simplePhrase.InputText)
            {
                _animator.SetBool(setAnimParameter.boolParameterName, setAnimParameter.BoolParameterInput);
                _setAnimParameters.Remove(setAnimParameter);
                break;
            }
        }
    }

    public override void Interact()
    {
        if (!DialogueViewer.IsGoing && _isInteractable)
        {
            if (_dialogueViewer != null)
            {
                StartCoroutine(_dialogueViewer.Starter());
                _isInteractable = false;
                _triggerCollider.enabled = false;
            }
                
        }
    }

    public override bool TrySelect()
    {
        if (_isInteractable && _dialogueViewer != null)
        {
            _interactiveSign.SetActive(true);
        }

        return _isInteractable;
    }
}

using System;
using System.Collections.Generic;

public class DialogueSetter
{
    private readonly DialogueBunch _dialogueBunch;
    private readonly List<DialogueBaseClass> _nextSimplePhrases;
    public static event EventHandler<AnswerActionEventArgs> OnAnswerAction;
    public static event EventHandler OnGoodResultDialogue;
    public class AnswerActionEventArgs : EventArgs
    {
        public bool isReputationAdded;
    }
    public DialogueSetter(DialogueBunch dialogueBunch)
    {
        _nextSimplePhrases = new List<DialogueBaseClass>();
        _dialogueBunch = dialogueBunch;
    }

    public DialogueBaseClass SetNewDialogue()
    {
        if (_dialogueBunch.Reputation < _dialogueBunch.MinReputation && _dialogueBunch.BadResultDialogue.Count!=0)
        {
            _dialogueBunch.CurrentDialogue = _dialogueBunch.BadResultDialogue;
            return _dialogueBunch.CurrentDialogue[0];
        }
        else if (_dialogueBunch.Reputation > _dialogueBunch.MaxReputation && _dialogueBunch.GoodResultDialogue.Count != 0)
        {
            _dialogueBunch.CurrentDialogue = _dialogueBunch.GoodResultDialogue;
            OnGoodResultDialogue?.Invoke(this, EventArgs.Empty);
            return _dialogueBunch.CurrentDialogue[0];
        }
        else if (_dialogueBunch.Reputation <= _dialogueBunch.MaxReputation && _dialogueBunch.Reputation >= _dialogueBunch.MinReputation && _dialogueBunch.MidResultDialogue.Count != 0)
        {
            _dialogueBunch.CurrentDialogue = _dialogueBunch.MidResultDialogue;
            return _dialogueBunch.CurrentDialogue[0];
        }
        else
        {
            _dialogueBunch.CurrentDialogue = null;
            return null;
        }
    }

    public DialogueBaseClass SetNewElementAtSimplePhrase(List<DialogueBaseClass> dialogue, DialogueBaseClass currentDialogueElement)
    {
        DialogueBaseClass nextDialogueElement = null;
        if (dialogue.Contains(currentDialogueElement))
        {
            if (dialogue[^1] == currentDialogueElement)
            {
                if (CheckListOfPhrases() == true)
                {
                    nextDialogueElement = _nextSimplePhrases[^1];
                    _nextSimplePhrases.RemoveAt(_nextSimplePhrases.Count - 1);
                    return nextDialogueElement;
                }
                else
                {
                    return null;
                }
            }

            nextDialogueElement = dialogue[dialogue.IndexOf(currentDialogueElement) + 1];
            return nextDialogueElement;
        }
        for (int i = 0; i < dialogue.Count; i++)
        {
            if (dialogue[i].TypeOfDialogue == TypeOfDialogue.Answers)
            {
                foreach (DialogueBaseClass.Answer answer in dialogue[i].Answers)
                {
                    nextDialogueElement = SetNewElementAtSimplePhrase(answer.NextDialogueBaseClasses, currentDialogueElement);
                    if (nextDialogueElement != null)
                    {
                        return nextDialogueElement;
                    }
                }
            }
        }
        return null;
    }

    public DialogueBaseClass SetNewElementAtAnswer(DialogueBaseClass nextDialogueElement, float addReputation, List<DialogueBaseClass> dialogue, DialogueBaseClass currentDialogueElement)
    {
        if (currentDialogueElement.TypeOfDialogue == TypeOfDialogue.Answers)
        {
            if(nextDialogueElement == null)
            {
                return SetNewElementAtSimplePhrase(dialogue, currentDialogueElement);
            }

            if(addReputation > 0)
            {
                OnAnswerAction?.Invoke(this, new AnswerActionEventArgs { isReputationAdded = true });
            }
            else
            {
                OnAnswerAction?.Invoke(this, new AnswerActionEventArgs { isReputationAdded = false });
            }
            _nextSimplePhrases.Add(SetNextSimplePhrase(_dialogueBunch.CurrentDialogue, currentDialogueElement));
            SetPreviousPhrases(_dialogueBunch.CurrentDialogue);
            _dialogueBunch.Reputation += addReputation;
            return nextDialogueElement;
        }
        return null;
    }

    private DialogueBaseClass SetNextSimplePhrase(List<DialogueBaseClass> dialogue, DialogueBaseClass currentAnswerElement)
    {
        DialogueBaseClass nextDialogueElement = null;
        if (dialogue.Contains(currentAnswerElement))
        {
            if (dialogue.Count > dialogue.IndexOf(currentAnswerElement) + 1)
            {
                nextDialogueElement = dialogue[dialogue.IndexOf(currentAnswerElement) + 1];
                return nextDialogueElement;
            }
            else
            {
                return null;
            }
        }

        for (int i = 0; i < dialogue.Count; i++)
        {
            if (dialogue[i].TypeOfDialogue == TypeOfDialogue.Answers)
            {
                foreach (DialogueBaseClass.Answer answer in dialogue[i].Answers)
                {
                    nextDialogueElement = SetNextSimplePhrase(answer.NextDialogueBaseClasses, currentAnswerElement);
                    if (nextDialogueElement != null)
                    {
                        return nextDialogueElement;
                    }
                }
            }
        }
        return null;
    }

    private void SetPreviousPhrases(List<DialogueBaseClass> dialogue)
    {
        if (dialogue.Contains(_nextSimplePhrases[^1]))
        {
            for (int i = 0; i < _nextSimplePhrases.Count - 1; i++)
            {
                if (dialogue.Contains(_nextSimplePhrases[i]))
                {
                    _nextSimplePhrases.Remove(_nextSimplePhrases[i]);
                }
            }
        }

        for (int i = 0; i < dialogue.Count; i++)
        {
            if (dialogue[i].TypeOfDialogue == TypeOfDialogue.Answers)
            {
                foreach (DialogueBaseClass.Answer answer in dialogue[i].Answers)
                {
                    SetPreviousPhrases(answer.NextDialogueBaseClasses);
                }
            }
        }
    }

    private bool CheckListOfPhrases()
    {
        if (_nextSimplePhrases == null || _nextSimplePhrases.Count == 0)
        {
            return false;
        }
        foreach(DialogueBaseClass el in _nextSimplePhrases)
        {
            if(el != null)
            {
                return true;
            }
        }
        return false;
    }
}

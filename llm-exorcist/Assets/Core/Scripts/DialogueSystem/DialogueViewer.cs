using Assets.Core.Scripts.PuzzleSystem;
using DG.Tweening;
using System;
using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class DialogueViewer : MonoBehaviour
{
    [Header("Dev settings")]
    [SerializeField] DialogueBunch _dialogueBunch;
    [SerializeField] private bool _isActiveOnStart;
    [SerializeField] private bool _isDestroyingInTheEnd = true;
    [Space(40), Header("Maintenance settings")]
    [SerializeField] private Canvas _dialogueCanvas;
    [Space(10)]
    [SerializeField] private Animator _dialogueAnimator;
    [SerializeField] private string _triggerForEndName;
    [Space(10)]
    [SerializeField] private TMP_Text _simplePhraseChamber;
    [SerializeField] private TMP_Text _nameChamber;
    [SerializeField] private TMP_Text _gradeChamber;
    [SerializeField] private ButtonContainer _answersChamberLayoutGroup;
    [Space(10)]
    [SerializeField] RectTransform _endGradeTransform;
    [SerializeField] Image _gradeLine;
    [SerializeField] float _durationForEndGradeMove;
    [SerializeField] float _ofsetForEndGradeView;
    [SerializeField] float _durationForEndGradeView;
    [Space(10)]
    [SerializeField, Tooltip("must contain MenuButton script")] private GameObject _answerButtonPrefab;
    private bool _isWriting = false;
    private bool _canResulting;
    private Vector2 _endGradePos;
    private Transform _answersChamberTransform;
    private Coroutine _writingCoroutine;
    private DialogueSetter _dialogueSetter;
    private DialogueWriter _dialogueWriter;

    public static event EventHandler OnCreditBookAction;
    public static event Action<DialogueBaseClass> OnPhraseChanged;
    public static event Action<PuzzleItemDataStruct> OnDialogueEnded;

    public static bool IsGoing { get; private set; } = false;
    public DialogueBaseClass CurrentDialogueElement { get; private set; }


    private void Start()
    {
        if (_answerButtonPrefab == null || _answerButtonPrefab.GetComponent<MenuButton>() == null)
        {
            Debug.LogError("GameObject dont have ButtonContainer or GameObjet dont initialised");
        }

        _answersChamberTransform = _answersChamberLayoutGroup.gameObject.transform;
        _endGradePos = _endGradeTransform.position;
        _dialogueSetter = new DialogueSetter(_dialogueBunch);
        _dialogueWriter = new DialogueWriter();

        if (_isActiveOnStart)
        {
            StartCoroutine(Starter());
        }
        else
        {
            _dialogueCanvas.gameObject.SetActive(false);
        }
    }

    private void Update()
    {
        if (IsCurrentViewerActive() && CurrentDialogueElement != null)
        {
            if (CurrentDialogueElement.TypeOfDialogue == TypeOfDialogue.SimplePhrases && (Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.E)) && _simplePhraseChamber.text.Length > 1)
            {
                if (_isWriting)
                {
                    _simplePhraseChamber.text = CurrentDialogueElement.simplePhrase.InputText;
                    _isWriting = false;
                    StopCoroutine(_writingCoroutine);
                }
                else
                {
                    CurrentDialogueElement = _dialogueSetter.SetNewElementAtSimplePhrase(_dialogueBunch.CurrentDialogue, CurrentDialogueElement);
                    ViewDialogue();
                }

            }
        }
    }

    public IEnumerator Starter()
    {
        if (!IsGoing)
        {
            _dialogueBunch.ResetBunch();
            CurrentDialogueElement = _dialogueBunch.CurrentDialogue[0];
            OnCreditBookAction?.Invoke(this, EventArgs.Empty);
            Reseter();
            _dialogueCanvas.gameObject.SetActive(true);
            IsGoing = true;
            yield return new WaitForSeconds(_dialogueAnimator.GetCurrentAnimatorStateInfo(0).length);
            ViewDialogue();
            if (_dialogueBunch.IsReputationable)
            {
                _gradeChamber.text = "...";
                _gradeLine.color = Color.clear;
            }
        }
    }

    private IEnumerator Ender()
    {
        Reseter();
        OnCreditBookAction?.Invoke(this, EventArgs.Empty);


        IsGoing = false;
        _dialogueAnimator.SetTrigger(_triggerForEndName);

        if (_dialogueBunch.PuzzleItemDatas.Count > 0)
        {
            foreach (PuzzleItemDataStruct puzzleItemData in _dialogueBunch.PuzzleItemDatas)
            {
                OnDialogueEnded?.Invoke(puzzleItemData);
            }
        }

        if (_dialogueBunch.IsReputationable)
        {
            ViewGrade(_dialogueBunch.Reputation, _gradeChamber);
            _gradeChamber.rectTransform.DOMove(_endGradePos, _durationForEndGradeMove);
            float duration;
            if (_dialogueAnimator.GetCurrentAnimatorStateInfo(0).length > _durationForEndGradeMove)
            {
                duration = _dialogueAnimator.GetCurrentAnimatorStateInfo(0).length;
            }
            else
            {
                duration = _durationForEndGradeMove;
            }
            yield return new WaitForSeconds(duration);
            yield return new WaitForSeconds(_ofsetForEndGradeView);
            _gradeChamber.DOFade(0, _durationForEndGradeView);
            _gradeLine.DOFade(0, _durationForEndGradeView);
            yield return new WaitForSeconds(_durationForEndGradeView);

            if (_dialogueBunch.Reputation < _dialogueBunch.MinReputation && _dialogueBunch.IsStatable)
            {
                GameStateManager.State = GameState.ExamsFailed;
            }
            else
            {
                GameStateManager.State = _dialogueBunch.NextGameState;
            }
        }
        else
        {
            if (_dialogueBunch.IsStatable)
            {
                GameStateManager.State = _dialogueBunch.NextGameState;
            }
            yield return new WaitForSeconds(_dialogueAnimator.GetCurrentAnimatorStateInfo(0).length);
        }
        _dialogueCanvas.gameObject.SetActive(false);
        if (_isDestroyingInTheEnd)
        {
            Destroy(gameObject);
        }
    }

    private void ViewDialogue()
    {
        StopAllCoroutines();
        Reseter();
        if (_dialogueBunch.IsReputationable)
        {
            ViewGrade(_dialogueBunch.Reputation, _gradeChamber);
        }

        if (CurrentDialogueElement != null)
        {
            if (CurrentDialogueElement.TypeOfDialogue == TypeOfDialogue.SimplePhrases)
            {
                _nameChamber.text = CurrentDialogueElement.simplePhrase.InputName;
                _writingCoroutine = StartCoroutine(_dialogueWriter.SimpleWritingText(CurrentDialogueElement.simplePhrase.InputText, _simplePhraseChamber, CurrentDialogueElement.SymbolTime, WritingTextCompletion));
                _isWriting = true;
                if (!_canResulting)
                {
                    _canResulting = _dialogueBunch.NecessaryPhrasesForResult.Contains(CurrentDialogueElement.simplePhrase.InputText);
                }

                OnPhraseChanged?.Invoke(CurrentDialogueElement);
            }
            if (CurrentDialogueElement.TypeOfDialogue == TypeOfDialogue.Answers)
            {
                for (int i = 0; i < CurrentDialogueElement.Answers.Count; i++)
                {
                    MenuButton currentAnswerButton = Instantiate(_answerButtonPrefab, _answersChamberTransform).GetComponent<MenuButton>();
                    DialogueBaseClass nextDialogueElement = null;
                    if (CurrentDialogueElement.Answers[i].NextDialogueBaseClasses.Count > 0)
                    {
                        nextDialogueElement = CurrentDialogueElement.Answers[i].NextDialogueBaseClasses[0];
                    }

                    float addReputation = CurrentDialogueElement.Answers[i].AddReputation;
                    currentAnswerButton.OnPressMethod.AddListener(() => SetNewElementAtAnswerBufer(nextDialogueElement, addReputation));
                    currentAnswerButton.OnPressMethod.AddListener(ViewDialogue);

                    //StartCoroutine(_dialogueWriter.SimpleWritingText(_currentDialogueElement.Answers[i].InputText, currentAnswerButton.TextChamber, _currentDialogueElement.SymbolTime));
                    currentAnswerButton.TextChamber.text = CurrentDialogueElement.Answers[i].InputText;
                    _answersChamberLayoutGroup.AddButton(currentAnswerButton.TextChamber);
                }
            }
        }
        else
        {
            if (_canResulting && _dialogueBunch.IsReputationable)
            {
                CurrentDialogueElement = _dialogueSetter.SetNewDialogue();
                if (CurrentDialogueElement != null)
                {
                    _canResulting = false;
                    ViewDialogue();
                }
                else
                {
                    StartCoroutine(Ender());
                }
            }
            else
            {
                StartCoroutine(Ender());
            }
        }
    }

    private void ViewGrade(float reputation, TMP_Text gradeChamber)
    {
        if (reputation > _dialogueBunch.MaxReputation)
        {
            gradeChamber.text = "5:)";
            _gradeLine.color = Color.red;
            return;
        }
        if (reputation < _dialogueBunch.MinReputation)
        {
            gradeChamber.text = "2;(";
            _gradeLine.color = Color.red;
            return;
        }
        if (reputation > (_dialogueBunch.MinReputation + _dialogueBunch.MaxReputation) / 2)
        {
            gradeChamber.text = "4";
            return;
        }
        if (reputation > (_dialogueBunch.MinReputation - _dialogueBunch.MaxReputation) / 2)
        {
            gradeChamber.text = "3..";
            return;
        }
    }

    private void SetNewElementAtAnswerBufer(DialogueBaseClass nextDialogueElement, float addReputation)
    {
        CurrentDialogueElement = _dialogueSetter.SetNewElementAtAnswer(nextDialogueElement, addReputation, _dialogueBunch.CurrentDialogue, CurrentDialogueElement);
    }

    private void WritingTextCompletion()
    {
        _isWriting = false;
    }

    private void Reseter()
    {
        _simplePhraseChamber.color = Color.white;
        _nameChamber.color = Color.white;
        _gradeChamber.color = Color.red;
        _gradeLine.color = Color.clear;
        _simplePhraseChamber.text = string.Empty;
        _nameChamber.text = string.Empty;
        _gradeChamber.text = string.Empty;
        foreach (Transform child in _answersChamberTransform)
        {
            _answersChamberLayoutGroup.Buttons.Clear();
            Destroy(child.gameObject);
        }
    }

    public bool IsCurrentViewerActive()
    {
        return IsGoing && _dialogueCanvas.gameObject.activeSelf;
    }
}

using Assets.Core.Scripts.PuzzleSystem;
using Core.Scripts.UI;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;

namespace Core.Scripts.PuzzleSystem
{
    /// <summary>Один блок пазла. Сообщает о перетаскивании менеджеру, сам ничего не перемещает.</summary>
    public class PuzzleItem : MonoBehaviour, IBeginDragHandler, IDragHandler, IEndDragHandler
    {
        [field: SerializeField] public bool IsActive { get; private set; }
        [field: SerializeField] public int OrderInSequence { get; private set; }
        [field: SerializeField] public PuzzleContainer ParentContainer { get; private set; }
        [SerializeField] private RectTransform _connectionAreaRect;

        [Header("Visuals")]
        [SerializeField] private TextMeshProUGUI _puzzleText;

        private RectTransform _rect;
        private HoverableObject _hoverableObject;
        private bool _isDragged;

        public PuzzleSpawner Spawner { get; private set; }
        public PuzzleGameManager Manager => Spawner != null ? Spawner.Manager : null;

        public RectTransform Rect
        {
            get
            {
                if (_rect == null) _rect = (RectTransform)transform;
                return _rect;
            }
        }

        /// <summary>Зона у нижнего края блока: если в неё попал верх перетаскиваемой цепочки, она встанет следом.</summary>
        public RectTransform ConnectionArea => _connectionAreaRect != null ? _connectionAreaRect : Rect;

        private void Awake()
        {
            TryGetComponent(out _hoverableObject);
        }

        public void Initialize(PuzzleSpawner spawner, PuzzleItemDataStruct data)
        {
            Spawner = spawner;
            IsActive = data.isActive;
            OrderInSequence = data.indexInSequence;

            if (_puzzleText != null)
            {
                _puzzleText.text = data.puzzleShortText;
            }

            if (_hoverableObject == null)
            {
                TryGetComponent(out _hoverableObject);
            }
            if (_hoverableObject != null)
            {
                _hoverableObject.SetHintText(data.puzzleText, data.puzzleInfo);
            }
        }

        public void SetContainer(PuzzleContainer container)
        {
            ParentContainer = container;
        }

        public void OnBeginDrag(PointerEventData eventData)
        {
            _isDragged = false;

            if (eventData.button != PointerEventData.InputButton.Left) return;

            var manager = Manager;
            if (manager == null || ParentContainer == null) return;

            if (_hoverableObject != null)
            {
                _hoverableObject.SetHoverTracking(false);
            }

            _isDragged = manager.BeginDrag(this, eventData.position);
        }

        public void OnDrag(PointerEventData eventData)
        {
            if (!_isDragged) return;

            Manager.Drag(eventData.position);
        }

        public void OnEndDrag(PointerEventData eventData)
        {
            if (!_isDragged) return;
            _isDragged = false;

            if (_hoverableObject != null)
            {
                _hoverableObject.SetHoverTracking(true);
            }

            Manager.EndDrag(eventData.position);
        }

        /// <summary>Середина верхней грани блока (в экранных координатах для Overlay-канваса).</summary>
        public Vector2 GetTopPoint()
        {
            var corners = new Vector3[4];
            Rect.GetWorldCorners(corners);
            return (corners[1] + corners[2]) / 2f;
        }
    }
}

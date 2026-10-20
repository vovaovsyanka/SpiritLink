using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace Core.Scripts.PuzzleSystem
{
    /// <summary>
    /// Вертикальная цепочка блоков. Только хранит блоки и следит, чтобы порядок в списке
    /// совпадал с порядком в иерархии. Логика перетаскивания — в <see cref="PuzzleGameManager"/>.
    /// </summary>
    public class PuzzleContainer : MonoBehaviour
    {
        [SerializeField] private List<PuzzleItem> _nestedPuzzles = new();
        [SerializeField] private GameObject _freeSpaceItemPrefab;

        private GameObject _freeSpaceItem;
        private RectTransform _rect;

        public IReadOnlyList<PuzzleItem> Puzzles => _nestedPuzzles;
        public int Count => _nestedPuzzles.Count;
        public PuzzleItem First => _nestedPuzzles.Count > 0 ? _nestedPuzzles[0] : null;

        public RectTransform Rect
        {
            get
            {
                if (_rect == null) _rect = (RectTransform)transform;
                return _rect;
            }
        }

        public int IndexOf(PuzzleItem puzzle) => _nestedPuzzles.IndexOf(puzzle);

        public void Add(PuzzleItem puzzle) => Insert(puzzle, _nestedPuzzles.Count);

        public void Insert(PuzzleItem puzzle, int index)
        {
            if (puzzle == null || _nestedPuzzles.Contains(puzzle)) return;

            index = Mathf.Clamp(index, 0, _nestedPuzzles.Count);
            puzzle.SetContainer(this);
            puzzle.transform.SetParent(transform, false);
            _nestedPuzzles.Insert(index, puzzle);
            SyncHierarchy();
        }

        public void Insert(IEnumerable<PuzzleItem> puzzles, int index)
        {
            foreach (var puzzle in puzzles)
            {
                Insert(puzzle, index++);
            }
        }

        /// <summary>Забирает блоки начиная с индекса. Вызывающий обязан сразу переместить их в другой родитель.</summary>
        public PuzzleItem[] TakeFrom(int startIndex)
        {
            if (startIndex < 0 || startIndex >= _nestedPuzzles.Count) return new PuzzleItem[0];

            var taken = _nestedPuzzles.GetRange(startIndex, _nestedPuzzles.Count - startIndex);
            _nestedPuzzles.RemoveRange(startIndex, taken.Count);
            foreach (var puzzle in taken)
            {
                puzzle.SetContainer(null);
            }
            return taken.ToArray();
        }

        public PuzzleItem[] TakeAll() => TakeFrom(0);

        /// <summary>Показывает пустое место после блока <paramref name="after"/> — сюда встанет перетаскиваемая цепочка.</summary>
        public void ShowFreeSpace(PuzzleItem after, Vector2 size)
        {
            HideFreeSpace();
            if (_freeSpaceItemPrefab == null) return;

            _freeSpaceItem = Instantiate(_freeSpaceItemPrefab, transform);
            _freeSpaceItem.GetComponent<RectTransform>().sizeDelta = size;
            SyncHierarchy(_nestedPuzzles.IndexOf(after) + 1);
            RebuildLayout();
        }

        public void HideFreeSpace()
        {
            if (_freeSpaceItem == null) return;

            // Destroy срабатывает только в конце кадра, поэтому сразу выключаем объект,
            // чтобы он не участвовал в layout и не сбивал индексы.
            _freeSpaceItem.SetActive(false);
            Destroy(_freeSpaceItem);
            _freeSpaceItem = null;
            RebuildLayout();
        }

        /// <summary>Суммарный размер цепочки: ширина самого широкого блока и сумма высот.</summary>
        public Vector2 GetContentSize()
        {
            var size = Vector2.zero;
            foreach (var puzzle in _nestedPuzzles)
            {
                var puzzleSize = puzzle.Rect.rect.size;
                size.x = Mathf.Max(size.x, puzzleSize.x);
                size.y += puzzleSize.y;
            }
            return size;
        }

        public void RebuildLayout()
        {
            LayoutRebuilder.ForceRebuildLayoutImmediate(Rect);
        }

        /// <summary>Приводит порядок детей в иерархии к порядку списка; свободное место ставит по индексу.</summary>
        private void SyncHierarchy(int freeSpaceIndex = -1)
        {
            for (int i = 0; i < _nestedPuzzles.Count; i++)
            {
                _nestedPuzzles[i].transform.SetSiblingIndex(i);
            }

            if (_freeSpaceItem != null)
            {
                if (freeSpaceIndex < 0) freeSpaceIndex = _freeSpaceItem.transform.GetSiblingIndex();
                _freeSpaceItem.transform.SetSiblingIndex(Mathf.Clamp(freeSpaceIndex, 0, _nestedPuzzles.Count));
            }
        }
    }
}

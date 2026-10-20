using Assets.Core.Scripts.PuzzleSystem;
using UnityEngine;

namespace Core.Scripts.PuzzleSystem
{
    /// <summary>Место в панели блоков, где лежит один блок и куда он возвращается.</summary>
    public class PuzzleSpawner : MonoBehaviour
    {
        [SerializeField] private GameObject _puzzleItemPrefab;

        public PuzzleGameManager Manager { get; private set; }
        public PuzzleItem SpawnedPuzzle { get; private set; }

        public void Initialize(PuzzleGameManager manager, PuzzleItemDataStruct data)
        {
            Manager = manager;

            var puzzle = Instantiate(_puzzleItemPrefab, transform).GetComponent<PuzzleItem>();
            puzzle.Initialize(this, data);
            SpawnedPuzzle = puzzle;

            Restore(puzzle);
        }

        /// <summary>Кладёт блок обратно в спавнер (в собственном контейнере).</summary>
        public void Restore(PuzzleItem puzzle)
        {
            Manager.InstantiateContainer(new[] { puzzle }, transform.position, transform);
        }
    }
}
